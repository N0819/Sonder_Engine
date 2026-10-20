"""ARRANGEMENT FIRST: the layout tier's core -- a building laid out from its
relations, storey by storey, in one deterministic solve (`solve_arranged`).

PROTOTYPE (lane "stepwise", 2026-10-15; merged that night with lane
"stacked"'s rule for storeys below the ground and a cross-storey lookahead
for windows above a stair; 2026-10-16 the storey below the ground dug, not
built -- earth where no room stands). It replaces the lab's randomized
division search (`layout_solver._search`) behind `layout_solver.solve_with`;
the lab keeps `solve`, and everything after the division -- doors, windows,
zones, furniture, grounds -- is the lab's, unchanged.

WHY. The lab's search places every stair hall first, as a hole, then divides
each storey around the holes at random and keeps the best of hundreds of
divisions; the bridge solved four seeds of it per building. Measured over the
owner's shrine (18 layouts, `sensible_check`, 2026-10-15): every layout failed
8 to 16 of 23 sensible checks -- stair halls soaking up floor (worst 6.1 times
their cap), flights laid end-on to the wall they were asked along (34 of 106
ends), stated sizes missed by a median 80%, 42 of 111 asked sides turned --
because nothing in the search starts from what the plan says lies next to
what. The owner asked for layouts "mostly right the first try": constructive
and deterministic, never generate-and-reject.

HOW (relational slicing: a guillotine tree built from the sides, after Otten
1982, sized exactly in integer paces by shape functions, after Stockmeyer
1983, with Medjdoub & Yannou's topological reduction for the sides):

  1. A STOREY IS A SLICING TREE BUILT FROM THE PLAN'S SIDES. Every room and
     stair hall of a storey is a leaf; a cut splits a set of leaves into a
     west and an east part, or a north and a south one. Two leaves the plan
     sets north and south of each other are never split by a west|east cut
     (they are glued), so every asked side holds by construction. A join
     across a cut makes the cut a wall of both its rooms, and so that the two
     share a wall whatever the sizes, one of them spans its part along the
     cut or both keep the same end of it (`_Storey._cross`).
  2. SIZES ARE ALLOCATED, NOT SEARCHED FOR. Each candidate tree is sized
     exactly by a shape-function DP: the least cost of laying a set of leaves
     in every w x h rectangle, a cut being the min-plus convolution of its two
     parts. The DP takes the minimum over every tree the relations allow
     (`_Storey.table`), so the cheapest arrangement and its sizes come out
     together -- and the ground storey's outline with them.
  3. STOREY BY STOREY. The ground storey is laid free, as one rectangle, its
     slack taken by the rooms that may grow (never a store) -- and since
     2026-10-19 its edge free to step: a room of it may leave open ground in
     its slot, a notch, a porch, an L (`NOTCH_COST`, the owner's ruling).
     Each storey above is laid inside the floor of the one below -- every room
     over a room or a stair hall, never over roof -- with the flights it shares
     with that storey pinned where they stand; floor it leaves is roof at its
     edge. A storey below the ground lies under the house's footprint, and
     is DUG, NOT BUILT: each of its rooms takes what it needs in the place
     the arrangement gives it, and the rest of its rectangle is earth -- no
     room, no floor (`EARTH_COST`). The
     ground's outlines that cost it about what its cheapest does are each
     carried forward, and the one whose other storeys give way least is
     kept; no other storey's rooms ever make a ground room larger
     (`_Building.lay_block`, `_weigh`).
  4. A STAIR HALL IS A ROOM OF THE ARRANGEMENT, its flight laid along the
     wall each end asks (never end-on), the hall at most `LANDING_MAX` paces
     longer than its flight -- below the ground also a landing beside it
     (`ACROSS_LANDING`); the room it serves keeps the end of the flight
     its storey is reached by, so the stair can be climbed foot to head.
  5. WHEN THE ASKS CONTRADICT, THE LOWEST GIVES WAY, and only what must
     (`_relaxed`), and the layout says so: a stair's wall, then an ordered
     join's order, then a join's side; on the ground only, the shared walls
     themselves; last a door outdoors -- never the entrance on the front,
     never a window, which is only priced (`RELAX_ORDER`). A storey below the
     ground never leaves the house's footprint: a cavern asked beyond a wall
     its stair or a room needs stands beyond another (`_cave_side`).
  6. NEVER WORSE THAN THE LAB (2026-10-19). The work is counted, never timed
     (`NARROW_WORK` a storey, `ARRANGE_WORK_BUDGET` a building): past the
     budget, or where nothing the rules allow lays the building, the core
     raises, and the bridge lays the building with the lab's own search as
     before the core (`layout_bridge.solve_for`), saying so.

Units are paces. Every cap and weight is a named constant below, with the
case that set it.
"""

from __future__ import annotations

import bisect
import copy
import json
import math
from dataclasses import dataclass, field

from world.layout_solver import (BLOCK_GAP, CORRIDORS, FLEXIBLE, MAX_GROWTH, PURPOSE_AREA, SEED, STAIR_FALLBACK,
                                 STAIRS, USE_SPACE, Division, Rect, _BEDS, _OPP, _SIDES, _STEP, _TABLES, _door_cells,
                                 _joins, _kind, _stated_area, fixture_footprint, purpose_key, room_target,
                                 solve_with)

INF = float("inf")

# ---------------------------------------------------------------- sides as bits
#
# A side set is a 4-bit mask, so a touch demand, an outline's sides and an
# orientation compare in one operation.

_BIT = {"n": 1, "e": 2, "s": 4, "w": 8}
_SIDE_OF = {1: "n", 2: "e", 4: "s", 8: "w"}
_OPPBIT = {1: 4, 4: 1, 2: 8, 8: 2}
_ALL = 15
_NS = 5
_EW = 10

# ---------------------------------------------------------------- the rules, named
#
# Shapes.

#: A corridor is this many paces wide (the owner's default for the tier,
#: 2026-10-15: "corridors take their axis from their joins and are 2 paces
#: wide"); its length is what its rooms need beside it.
CORRIDOR_WIDTH = 2
#: The shortest corridor: a corridor shorter than this is a landing.
CORRIDOR_MIN_LENGTH = 3
#: A stair hall runs at most this many paces past its flight, along the run
#: (the owner's default: spare floor goes to "stair landings (at most 2
#: paces along the run)"). Below the ground the lab's halls took a landing up
#: to 9.1 times their flight (`_absorb` capped it only above the ground).
LANDING_MAX = 2
#: A flight at least this long runs along a wall and lands along its run; a
#: shorter stair (a ladder, a spiral) has no run to land along.
STRAIGHT_RUN = 3
#: ...and its hall takes at most this many cells round it (the sensible
#: check's landing: max(4, half the flight)).
SHORT_LANDING = 4
#: What one cell of landing costs: dearer than a flexible room growing,
#: cheaper than a service room growing past its band, so slack reaches a
#: landing only after the rooms that may take it.
LANDING_COST = 1.2
#: A stair hall is at least this many paces across, whatever its flight: a
#: ladder is a pace wide, but the world reads no place narrower than two
#: (`spatial_geometry.EXTENT_MIN_PACES`).
HALL_MIN_ACROSS = 2
#: A STAIR HALL MAY TAKE A LANDING PAST ITS CAP WHERE THE LANDING BUYS
#: SOMETHING (the fix round's phase 2, 2026-10-19: the unseen plans' finding
#: 3, the code review's finding 9). The storey laid first is one rectangle
#: wholly floor cut by guillotine cuts, so a room sharing a hall's band --
#: the row or column a cut gives the hall -- was cut to the hall's own depth
#: or width wherever no other leaf filled the band, the cap being a hard
#: bound and a stated size only a price: the unseen farmhouse's byre, stated
#: 36 m2, laid 8.4 m2 beside its ladder's hall; the inn's taproom a third
#: short beside its cellar steps; a room and a straight stair asked on one
#: wall unable to share it (the code review's e26). Past the cap -- along
#: the run past LANDING_MAX, or across it -- the hall's cells cost
#: LANDING_OVER_COST each besides a landing's own LANDING_COST, so the DP
#: lays one only where a room's stated or needed size, or an asked side,
#: would cost more than those cells: never as free slack, which a room
#: growing takes more cheaply. Only on a storey laid wholly floor (above the
#: ground roof fills a hall's band, below it earth). At most
#: LANDING_OVER_CEILING times the hall's least area. The sensible check's
#: stair_hall_size reads such a hall as past its cap -- it is. The price is
#: what keeps it from being slack: at 3 a ladder's hall in a small house
#: took two cells past its cap for nothing a check sees, an unstated room a
#: shade nearer its target (the code review's e12b-d and e36b, 15 of the 17
#: generated plans whose ladder hall passed its cap); at 6 those halls keep
#: to their cap and every hall that bought a stated size keeps it -- the
#: byres, the clamped taproom, the inn's cellar steps, the farmhouse; at 10
#: the clamped taproom and the stacked rooms over corridors lose theirs
#: (the price sweep, 2026-10-19, 48 specs).
LANDING_OVER_COST = 6.0
LANDING_OVER_CEILING = 4
#: ABOVE THE GROUND A PINNED HALL KEEPS THE LANDING ITS HALL BELOW TOOK
#: BESIDE ITS RUN (the fix round's phase 2: the unseen watchtower's finding
#: 6, and the landing past the cap above). The flight climbs out of that
#: landing's floor, so the storey above stands over it: a hall that is its
#: flight alone left the cells beside it roof -- a 1.5 m square notch beside
#: the watchtower's spiral, three storeys deep -- and where the landing ran
#: between the flight and the corridor it serves (the hospital's main stair,
#: its hall taking a row in front of its flight), the corridor above could
#: not meet the flight at all. Never past the run's ends: there a room meets
#: the landing and not the flight (the shrine's hallway, 8 of 18 runs). Each
#: cell kept costs KEPT_LANDING_COST -- a shade under a full storey's roof
#: (PAD_UPPER), so a storey keeps its whole outline over its stair; above
#: under-the-roof storeys roof (PAD_ROOF) is cheaper and wins. ON A STOREY
#: OF ONE ROOM THAT RISES SHEER (`_sheer_box`) the landing is kept whole, not
#: priced: no other room can stand over it, so roof there is a notch beside
#: the stair however cheap -- the watchtower's chamber, watch room and beacon
#: each kept theirs as a light well for the window they ask on the stair's
#: wall (WINDOW_COST outbid the price), and the tower did not rise sheer.
KEPT_LANDING_COST = 1.0
#: A LANDING CELL PAST THE END OF A PINNED FLIGHT ITS STOREY DOES NOT TAKE is
#: one no body on that storey reaches without crossing the flight (the
#: review's visual 3): below the ground, where a dug storey's pinned hall
#: lands, each such cell costs this -- waste, dearer than earth beside it
#: (the review's dead_landing: sealed cells 100 to 80 on the 18 shrines).
DEAD_LANDING_COST = 6.0
#: The narrowest room, by what it is for: a closet, a washroom or an entry
#: may be two paces across (the world's own minimum place); a room people
#: live in, three.
SMALL_PURPOSES = ("toilet", "latrine", "closet", "entryway", "bath", "washroom", "storage")
MIN_SIDE_SMALL = 2
MIN_SIDE_ROOM = 3
#: ...and a small room two paces across still costs this much: narrow is
#: allowed, not sought.
THIN_COST = 4.0
#: Proportions: a room up to ASPECT_FREE long for its width costs nothing;
#: to ASPECT_SOFT (the sensible check's 2.5:1) ASPECT_COST per unit; past it
#: ASPECT_STEEP per unit; past ASPECT_MAX it is no room. A corridor is exempt.
ASPECT_FREE = 2.0
ASPECT_SOFT = 2.5
ASPECT_MAX = 3.2
ASPECT_COST = 8.0
ASPECT_STEEP = 100.0

# Sizes. A size the description STATES (area_m2) is laid within
# STATED_BAND of it where the arrangement allows; past the band it is priced
# steeply (the owner's default, 2026-10-15). A room the description leaves
# unsized aims at the solver's own `room_target(stated=False)`: a service
# room keeps it, a flexible one (`FLEXIBLE`) may grow toward its ceiling
# (PURPOSE_AREA hi x MAX_GROWTH) when the storey has floor to spare.

STATED_BAND = 0.15
#: ...within this many cells of a small stated size counts as within the band
#: (two cells is one row of a two-pace room).
STATED_SLACK = 2.0
W_STATED = 10.0           # per unit |ln(area / stated)|, inside the band
W_STATED_OUT = 80.0       # ...and per unit past it: 30% off costs about 12
W_STATED_OUT_FLEX = 20.0  # ...a flexible room growing past it, toward what its things need
W_STATED_OUT_FLEX_PAST = 40.0  # ...and past what its things need
KEEP_BAND = 0.25          # an unsized room's own band, inside the check's 30%
KEEP_SLACK = 3.0          # ...or this many cells of a small target
W_KEEP = 6.0
W_KEEP_OUT = 40.0
GROW_BAND = 0.25          # a flexible room grows this far cheaply
W_GROW = 1.5
W_GROW_MID = 8.0          # ...then dearer to its ceiling
W_CEILING = 60.0          # ...and steeply past it
CORRIDOR_SIZE_W = 1.0     # a corridor's length follows its rooms: weakly sized
CORRIDOR_LENGTH_COST = 0.1

#: A floor thing the room's rectangle cannot take where it was asked, with
#: its use space (the sensible check's `room_holds_fixtures`): FIT_COST when
#: not even at its plain size, FIT_PLAIN_COST when only there. Capped per
#: room at FIT_CAP so a room whose plan asks the impossible still has a size.
FIT_COST = 10.0
FIT_PLAIN_COST = 2.0
FIT_CAP = 60.0
#: Under the roof (a storey marked smaller) a thing and its use strip must fit
#: across the room's depth, not wall to wall between the eaves.
DEEP_COST = 8.0

# The arrangement.

#: A window the plan puts on a side whose room no longer reaches that side of
#: the outline (where it could look out).
WINDOW_COST = 12.0
#: CROSS-STOREY LOOKAHEAD FOR A WINDOW ABOVE A STAIR: a room above the
#: ground asks a window on the wall a flight arrives along (the roost's south
#: gable window, its stair asked on that same wall). It keeps both only by
#: running past the flight's end onto roof, one cell a window -- roof over
#: floor of the storey below. So the storey that lays the flight first gives
#: its hall a landing that long along the run (at most LANDING_MAX), each
#: cell short costing WINDOW_LANDING_COST: dearer than the landing's own
#: cells (LANDING_COST each), so the hall takes it unless the storey cannot
#: (the stepwise lane: the roost's window turned north on 2 of 14 shrine
#: runs, its storey below leaving no floor beside the flight).
WINDOW_LANDING_COST = 6.0
#: A room that opens outdoors on no named side, standing wholly inside.
OUTWARD_ANY_COST = 30.0
#: Roof: floor a storey above the ground leaves at its edge, per cell -- under
#: the roof (a smaller storey) cheaply, on a full storey dearer than a room
#: growing.
PAD_ROOF = 0.4
PAD_UPPER = 1.2
#: A FULL STOREY KEEPS TO THE WALLS BELOW IT (the fix round's phase 3: the
#: unseen plans' finding 8): a strip of roof at most LEDGE_DEPTH paces deep
#: running the whole length of an outer wall of a storey above the ground
#: not marked smaller -- left inside its outline (a pad along a whole side)
#: or outside it (the outline set back from the floor below) -- costs
#: LEDGE_COST a cell besides its roof, about what a room past its band pays
#: (the unseen inn's first floor stood a pace in from the ground's whole west
#: front, 13 cells of ledge at PAD_UPPER cheaper than one guest room grown
#: 27%). Deeper, it is a terrace or a wing, the storey truly smaller.
LEDGE_COST = 2.0
LEDGE_DEPTH = 2
#: The deepest strip of roof one node of the tree may leave on one side.
PAD_MAX = 10
#: THE GROUND'S OUTLINE MAY STEP (the owner's ruling for the fix round's
#: phase 3, 2026-10-19: "the house's outline may step -- a porch, a notch,
#: an L -- rather than rooms leaving the sides the plan asks"). The ground
#: was one rectangle wholly floor, so its spare floor had nowhere to go but
#: the room that spans a depth alone: over the shrine's 18 layouts the bath
#: ran the ground's whole depth in 18, was as large as the main hall in 17,
#: the main hall a 4-pace strip in 14 (the review's visual 2). A ROOM OF THE
#: GROUND MAY LEAVE OPEN GROUND IN THE SLOT THE ARRANGEMENT GIVES IT: one
#: strip on one side of it, a NOTCH -- open ground, never a room, never
#: named, outside the house's walls (`Layout.notches`) -- lying along the
#: outline and short of it at one end at least (an L; a recess along a
#: side), or run from the outline into the house between rooms (a porch;
#: `_Storey._notched`). Each cell costs NOTCH_COST: dearer than a flexible
#: room growing within its band (W_GROW, a few hundredths a cell), cheaper
#: than a service room past its band (about 46/area a cell past KEEP_BAND,
#: about 1.0 for a bath of 45 cells), so spare floor still goes to the rooms
#: that may take it and a notch is left only where a room would otherwise
#: span a depth or a width it does not need. Each reflex corner a notch
#: makes costs NOTCH_STEP_COST, so one is made only where it buys a room
#: nearer its size or proportion, or a heart room its wall to the outside
#: (HEART_DARK_COST); a ground laid with more than GROUND_STEPS_MAX reflex
#: corners, or parting rooms the plan joins, is laid again with dearer
#: corners and else wholly floor (`lay_free`). A notch is at least
#: NOTCH_MIN_SIDE paces across both ways (the world reads no place narrower:
#: `spatial_geometry.EXTENT_MIN_PACES`), a notch open on one side runs at
#: most NOTCH_ASPECT times its opening into the house -- a step or an L,
#: never a slot -- and is never left by a room it would bring below its
#: target, by a corridor or by a stair hall, nor on a side the room must
#: keep -- a join across, a span, a building beyond -- save an outline side
#: kept only for a door outdoors: the door then opens onto the notch, a
#: porch before it.
NOTCH_COST = 0.8
NOTCH_STEP_COST = 6.0
#: ...and a room leaves at most this many times its own floor as a notch: a
#: closet's slot is not a yard, and the bound keeps the ground's tables
#: nearer the size they had wholly floor. (At 2 a genkan of 6 cells could
#: not leave the 14 beside it that gave a skeleton of the shrine's main hall
#: its wall to the garden, and the hall came out 3 x 3 and dark.)
NOTCH_SHARE_MAX = 3.0
NOTCH_MIN_SIDE = 2
NOTCH_ASPECT = 2.0
GROUND_STEPS_MAX = 2
#: ...and a ground whose notches pass it is laid again with each reflex
#: corner this many times as dear before it is laid wholly floor
#: (`lay_free`).
NOTCH_RETRY_FACTOR = 4.0
#: ...and of a ground with storeys above or below it, at most this many
#: grounds laid with notches are carried beside those laid wholly floor
#: (`_carry`): each carried ground lays every storey of the block again --
#: carried as many as the plain ones (LOOKAHEAD), the shrine's relays took
#: three times as long, and the chain kept a plain ground on 14 of 18.
NOTCH_LOOKAHEAD = 2
#: ...and only where laying it wholly floor built fewer than this many table
#: entries (`_Meter`): a ground with notches builds one and a half to three
#: and a half times as many (the shrine 25 k against 14 k, the unseen
#: hospital 89 k against 25 k), and the unseen merchant's ground alone built
#: 1.05 M wholly floor -- laid twice it would pass the core's whole budget
#: (ARRANGE_WORK_BUDGET) and go to the lab's search.
NOTCH_WORK = 400_000
#: THE HEART OF THE HOUSE KEEPS A WALL TO THE OUTSIDE (the review's visual
#: 1): a living room, a hall or a common room of the ground storey with no
#: wall on the outline costs this, and a notch a room alone across a cut
#: from it runs from the outline beside it takes it back (LIT_EW, LIT_NS --
#: a notch elsewhere that happens to touch it is not counted). In 13 of 14
#: shrine runs the main hall had no outside wall, its plan asking a
#: neighbour on every side; laid as one rectangle wholly floor no price
#: could give it one (the review's daylight experiment, OUTWARD_ANY_COST,
#: changed none of 18). With the outline free to step, a neighbour across a
#: cut from it may leave a notch beside it -- the porch beside a genkan --
#: and the main hall faces the garden there.
HEART_DARK_COST = 30.0
HEART_PURPOSES = ("living", "hall", "common_room")
#: A touch-demand bit (above the four side bits) asking a ground room laid
#: alone across a cut from a dark heart room to leave its notch beside it:
#: LIT_EW -- its notch on its west or east side, across a north|south cut;
#: LIT_NS -- on its north or south side, across a west|east cut.
LIT_EW = 16
LIT_NS = 32
#: A storey below the ground lies UNDER THE HOUSE'S FOOTPRINT (the owner's
#: rule, 2026-10-15) -- only one that cannot lie there with every ask that
#: may give way given (never measured on any plan) may reach this many
#: paces past it, at BEYOND_COST a cell, with a warning.
BELOW_REACH = 14
BEYOND_COST = 0.6
#: A BLOCK THAT STANDS ONLY BELOW THE GROUND (a cavern) opens off a room of
#: the basement storey it stands beside, beyond the wall the plan asks. The
#: basement lies under the house, so where a stair or a room the plan asks
#: needs that wall, THE CAVERN'S SIDE GIVES WAY: it stands beyond another
#: wall of that room the storey leaves exposed (`_cave_side`), and a warning
#: names it -- never the footprint (the stepwise lane laid the basement north
#: of the house on 11 of 14 shrine runs: its cavern block's side was a
#: demand no ask could outrank, so the cellar stair's wall gave way and the
#: storey stood beyond its flight). The asked side lost costs CAVE_SIDE_COST
#: -- below a stair wall's RELAX_COST (20), so a stair asked on that wall
#: keeps it -- and the room left with no wall on its storey's outline at
#: all, nowhere for the cavern to open, CAVE_ANY_COST.
CAVE_SIDE_COST = 12.0
CAVE_ANY_COST = 100.0
#: A storey below the ground lies under the rooms its stairs join on the
#: storey above where it can: each of its cells under none of them costs
#: this much -- a tie-break, far below any room's size (lane A's 0.05).
UNDER_COST = 0.05
#: AN UPPER ROOM STANDS OVER THE ROOMS ITS STAIR CLIMBS FROM where it can
#: (the fix round's phase 2: the unseen farmhouse's hayloft, "over the byre,
#: reached only by the ladder from the byre", stood over the house place):
#: each cell of a room above the ground over none of the rooms the stair
#: reaching it joins on the storey below costs this -- the tie-break
#: UNDER_COST is for a storey below the ground, read per room, far below any
#: room's size. Only a room its stair is the only way into: a room joined to
#: others on its storey stands where those joins put it, and read on the
#: absolute extents every set holding one cost the pinned DP twice the
#: work (the shrine's hallway: its relays a third slower, no layout changed).
OVER_COST = 0.05
#: BELOW THE GROUND A STOREY IS DUG, NOT BUILT (the owner's rule,
#: 2026-10-16). Its rooms stand under the house's footprint, as above; the
#: cells of its rectangle that no room takes are EARTH -- not a room, not
#: floor: no door, no name, never walked or furnished, never counted as a
#: room (`layout_solver.Layout.earth`). Each room and stair hall of a dug
#: storey takes the shape it needs inside the place the arrangement gives
#: it, the rest of that place earth (`_Storey._earth_rel`, `_earth_abs`);
#: a room no longer reaching the outline on a side loses what it asked of
#: that wall -- a window, a block beyond it (a cavern) -- as a cut taking
#: the side would (`_Storey._lost_sides`). Earth costs EARTH_COST a cell: dearer than nothing,
#: so a dug storey is no larger than its rooms need; cheaper than a
#: landing's cell (LANDING_COST) or a room grown past its band, so a stair
#: hall below the ground is its flight and the rooms the plan names take
#: what they need; and far below any ask, so earth is left where it buys
#: one -- a side, a stated size, a cavern's wall -- and never to make a
#: room smaller than its target. (Under a storey wholly floor a two-room
#: basement was no wider than its stair hall: the shrine's cavern, asked
#: beyond the basement's north wall, stood off a side wall on 12 of 14
#: runs, and a basement stated at 80 m2 was laid at 27.6 m2 -- the merge
#: lane, 2026-10-15.)
EARTH_COST = 0.1
#: A room of a dug storey stands against the sides of its slot where it
#: can: each pace off them costs this -- a tie-break, so that among places
#: alike the flush ones are read first (`_Storey._earth_rel`).
EARTH_SHIFT = 0.001
#: BELOW THE GROUND A FLIGHT MAY LAND BESIDE ITS RUN: its hall this many
#: paces deeper than the flight along the flight's whole length, the cells
#: within the sensible check's one landing (max(SHORT_LANDING, half the
#: flight)) -- so a room standing at the end of the flight its storey does
#: not take reaches the end it does across that landing, and need not
#: stand beyond the flight's foot. The flight a cellar is reached by comes
#: down along the house's edge, and the ground's room takes its head: its
#: foot lies in the house's corner, and a basement that must stand beyond
#: the foot stands south of the flight with the flight along its far wall
#: (13 of the 14 shrine runs, the earth lane's measure). 0: never.
ACROSS_LANDING = 1
#: The end code (`_Storey._cross`) of a room that reaches the end of a
#: flight its storey takes across the landing beside the run: its wall
#: shares a cell with that landing (`_chk_cost`).
ACROSS_END = 32
#: The ground outline: longer than OUTLINE_ASPECT for its depth costs
#: OUTLINE_COST per unit.
OUTLINE_ASPECT = 2.0
OUTLINE_COST = 6.0
#: A flight a storey lays first climbs to a room that must stand over this
#: storey's floor beside its hall: each cell of the SUPPORT_DEPTH-deep strip
#: on that side of the hall that is not floor costs SUPPORT_HINT
#: (`_support_hint`) -- the beam's look-ahead for the storey above.
SUPPORT_DEPTH = 3
SUPPORT_HINT = 4.0
#: The share of its own cost each storey but the ground adds to the total by
#: which the ground's outline is chosen (`_weigh`): what it gives way counts
#: in full.
FITTED_WEIGHT = 0.2
#: A storey above the ground that can only stand over roof (every ask that
#: may give way given) costs this much a cell of it not over a room; and a
#: storey below the ground laid beyond the house's footprint this much more
#: than its cells -- so a carried state that keeps the owner's rules wins.
UNSUPPORTED_COST = 25.0
BEYOND_FLAT = 20.0
#: The beam, for each ground outline carried: each storey after the first
#: is laid in its BEAM_EACH cheapest ways on every carried state, and the
#: BEAM cheapest states carried on (a roof storey needs floor where the
#: storey below may have chosen roof). A chain already dearer than the best
#: finished one is dropped.
BEAM = 3
BEAM_EACH = 2
#: The straight flights a storey lays first are laid both ways round (which
#: end its room reaches), at most END_SHAFTS of them a storey: 2 to the
#: power END_SHAFTS layouts carried.
END_SHAFTS = 2
#: How many of the ground storey's cheapest outlines are carried forward and
#: laid with every other storey before one is kept.
LOOKAHEAD = 8
#: ...and of a large building (a storey of more than LARGE_STOREY leaves).
LOOKAHEAD_LARGE = 2
#: ...drawn from the cheapest outline of each depth and of each width within
#: this much of the cheapest ground for itself: grounds that cost it about
#: the same, among which the storeys above choose. Never more: a ground
#: room is never made larger to carry the storey above (the owner's
#: default, 2026-10-15) -- at 150 the shrine of clone 168 #2 took a ground
#: 37 dearer for itself, its main hall and kitchen each a third past their
#: stated sizes, so that its first storey gave way fewer asks.
LOOKAHEAD_MARGIN = 10.0
#: THE GROUND GROWS ONLY WHERE THE STOREYS ABOVE CANNOT OTHERWISE BE LAID
#: (the fix round's phase 1, 2026-10-19: the code review's finding 2, the
#: unseen plans' finding 2). Where no carried ground holds the storeys above
#: or below it -- every chain dropped, which, a shared wall never given way
#: off the ground (GROUND_ONLY), means a storey whose rooms could not all be
#: reached, or the building refused -- the block is laid again carrying
#: LOOKAHEAD_GROW times as many ground outlines, from within
#: LOOKAHEAD_MARGIN_GROW of the cheapest. THE OWNER'S RULE THAT NO GROUND
#: ROOM IS MADE LARGER TO CARRY THE STOREY ABOVE YIELDS THERE AND ONLY THERE
#: -- the alternative is unreachable rooms or a refusal -- and the layout
#: says so. (The inn without its office: its upper corridor lost four rooms
#: and its stair on every ground within 10 of the cheapest, two outlines
#: carried for each way round its two flights; carrying 32 from within 150
#: laid it with no breach. A top-heavy house -- an entry and a kitchen under
#: five bedrooms -- raised: no ground within 10 could hold its upper floor.)
LOOKAHEAD_GROW = 4
LOOKAHEAD_MARGIN_GROW = 150.0
#: ...those outlines at least as large as the storey beside it needs: each
#: room this share of its target, each stair hall its least hall
#: (`_floor_needed`).
GROW_FLOOR_SHARE = 1.0 - KEEP_BAND
#: ...and where a storey beside the ground lays a room the plan sizes at less
#: than this share of its size (the sensible check's own 30%), the block is
#: laid again on more grounds too (`_Building._crushed`).
CRUSHED_SHARE = 0.70
#: ...but only where that storey is crowded: its rooms at their sizes (each
#: room the plan sizes at that size, every other its target) and its stair
#: halls need at least this share of the ground's floor -- a storey that has
#: floor to spare and crushes a room anyway crushes it by how it is
#: arranged, and a larger ground does not help it (the shrine's clone 168
#: #2 and its s1: rooms needing 52% and 41% of the ground's floor, Hinami's
#: room laid at half its size, the ground grown for 4.5 s and 3.6 s and kept
#: as it was; the unseen inn without its office: 95%, and its upper rooms
#: came back to size).
CROWDED_SHARE = 0.80
#: ...and laid again on LOOKAHEAD times this many grounds, not
#: LOOKAHEAD_GROW: a chain that reached every room needs a ground a little
#: larger, not one of the widest search (the unseen inn without its office:
#: carried 32 grounds its crushed rooms took 14.4 s; 16 found the same 20 x
#: 11 ground in 4.1 s; 8 did not find it).
LOOKAHEAD_GROW_CRUSHED = 2
#: Bipartitions of one set of leaves tried per axis, and joined-group touch
#: variants per bipartition: past these the most balanced are kept. Bounds
#: the work on a large storey (the manor's ground floor: twelve rooms).
CUT_CAP = 12
VARIANT_CAP = 4
#: A building of more than LARGE_BUILDING rooms -- past the tier's own cap
#: (`layout_bridge.LAYOUT_TIER_MAX_ROOMS`), so laid only when asked directly
#: -- lays every storey as a large storey is laid.
LARGE_BUILDING = 24
#: A STOREY that has built NARROW_WORK table entries -- one storey of one
#: block, over every way it was tried and every carried state it was laid on
#: -- is laid on as a large storey is laid, from that entry on, mid-solve
#: (`_Storey._tick`): a count, so the solve stays the same on every machine
#: (the manor's attic, its sides given way, explored every slicing tree of
#: six leaves at 15 to 30 s a try). Counted per storey since 2026-10-19:
#: counted per building, a costly ground left every storey above it narrow
#: from its first entry (the unseen merchant's house: its ground built 2.03 M
#: entries, and all 76 of its first storey's problems were laid narrow), and
#: read only when a storey problem was made, one storey's DP was never
#: bounded (the code review's six rooms joined with no side asked: 46 s,
#: 1 GB, one try). 1.5 M until 2026-10-19; at 1.0 M the merchant's ground
#: (9 leaves, the most work of any storey measured) is laid the same, cell
#: for cell, in 44 s and 0.66 GB against 50 s and 0.75 GB, and no other
#: storey of the shrine's 18, the 7 unseen or the review's specs reaches it
#: (the next most, 0.87 M: the inn without its office, upper floor).
NARROW_WORK = 1_000_000
#: ...and a storey with a join between two rooms asked no side, sooner: past
#: NARROW_WORK_OPEN. No side leaves every cut between the pair open, and each
#: such join multiplies the ways the search reads (the code review's grids,
#: rooms joined to their neighbours with no side asked: six rooms built 2.3 M
#: entries in 76 s and 1.1 GB searched wide, 0.31 M in 7 s and 0.18 GB
#: narrowed past 0.2 M, every join kept; eight rooms ran past 1.6 GB, now
#: 9 s and 0.24 GB; a plausible house with three sides missing, 0.9 GB and a
#: MemoryError against 4.4 s and 0.22 GB). No plan measured -- the shrine's
#: 18, the 60 generated, the 7 unseen -- holds one: the plans and the relate
#: answers side their joins, and `spec_from_answers` leaves one unsided only
#: where neither does.
NARROW_WORK_OPEN = 200_000
#: THE CORE'S WHOLE BUDGET, in table entries over the whole building: past
#: it the core stops (`ArrangeBudget`) and the bridge lays the building with
#: the lab's search, as before the core (`layout_bridge.solve_for`). Counted
#: like NARROW_WORK, never timed, so which path lays a building is the same
#: on every machine. A table entry costs 30 to 50 us and, while its storey
#: is laid, about 550 bytes: the budget is about 1.1 GB and 60 to 100 s of
#: the core at the worst. Measured 2026-10-19 on this core: the shrine's 18
#: layouts 18 k to 117 k entries, the 7 unseen plans 1 k (the townhouse) to
#: 1.32 M (the merchant's house, 44 s, 0.66 GB), the review's six rooms with
#: no side asked 0.31 M. (On the earth tree, before the tables were shared
#: and let go, the inn alone built 1.70 M in 54 s and 0.87 GB, and the
#: merchant's house ran out of 1.6 GB.) Named per ask-before-limiting.
ARRANGE_WORK_BUDGET = 2_000_000
#: ...and on a storey of more than LARGE_STOREY leaves, these.
LARGE_STOREY = 9
CUT_CAP_LARGE = 2
VARIANT_CAP_LARGE = 1
DOWNSET_LIMIT_LARGE = 256
LEAF_MARGIN_LARGE = 40.0
KEY_CAP_LARGE = 4
#: Paces of wall two joined rooms share at least where a coupled cut must
#: check it (a doorway and its jamb); a stair hall and the room it serves
#: along its run share ALONG_SHARED (the sensible check's 'along': half the
#: shorter of the run and the wall), and the room reaches an end of the
#: flight (ALL_ENDS: either).
MIN_SHARED = 2
ALONG_SHARED = 3
#: A room meeting a corridor at its stair's end by fewer than MIN_SHARED
#: paces costs its storey this (`_Storey._min_shared`, `_chk_cost`): a
#: price, not a rule, so the two paces hold wherever they cost the storey
#: less and yield to a stated size of the ground (the lab's runs 2 and 3:
#: held as a rule, their main hall came out 41% past its size; priced at 8,
#: run 3's still did, the storey above dearer on the ground that kept it;
#: at 4 both lay it within 12% -- measured 2026-10-19).
HEAD_SHARED_COST = 4.0
ALL_ENDS = 16
#: Down-sets of one set of atoms kept, best first, before the cuts are read
#: (`_downsets`); DOWNSET_LIMIT_LARGE on a large storey.
DOWNSET_LIMIT = 4096
#: THE DOWN-SETS OF A SET OF AT MOST DOWNSET_EXACT_ATOMS ATOMS ARE ENUMERATED
#: WHOLE (2 ** 14 sets at most), and only then ranked -- the fewest joined
#: pairs across the cut, then the most balanced -- and cut to the limit;
#: past it they are grown, each from one atom (`_grown`). A walk stopped at
#: the limit kept only sets of the last atoms in leaf order: on a storey of
#: eleven rooms, a hall spelled 'a_hall' could never stand west or north of
#: the root cut and the storey could not be laid, while the same plan with
#: 'z_hall' laid (the code review's e35, 2026-10-16).
DOWNSET_EXACT_ATOMS = 14
#: Extents kept per shape of a node an ancestor's coupled cut reads: the
#: cheapest KEY_CAP. Bounds the coupled tables; past it the dearest ways of
#: placing the tracked rooms are not offered.
KEY_CAP = 12
#: A table entry dearer than its node's cheapest by more than this is dropped;
#: a leaf's shapes dearer than its cheapest by more than LEAF_MARGIN too.
PRUNE_MARGIN = 250.0
LEAF_MARGIN = 150.0
#: A storey laid inside a region tries outlines no larger than its leaves
#: take within REGION_SPREAD of their cheapest shapes, and, where roof (or,
#: below the ground, earth) may be left, REGION_ROOF more: bounds the
#: outlines tried on a large region. (A dug storey's outline came out the
#: same on all 18 shrine layouts with 0, 0.25, 0.6 or 1.0 more.)
REGION_SPREAD = 40.0
REGION_ROOF = 0.6
#: ...and solves at most REGION_TRIES of them, the cheapest-bound first, and
#: the region's own bounding box besides: each outline tried is a whole
#: pinned DP, and an attempt no outline holds paid for every one (the unseen
#: merchant's 19 x 17 floor: 882 rectangles holding its pin).
REGION_TRIES = 160
#: The order in which contradicting asks give way on a storey that cannot
#: hold them all, lowest first (the owner's default, 2026-10-15): the end a
#: stair is reached by, a stair's wall, an ordered join's order, a join's
#: side; then the shared walls themselves -- a stair hall's with its room,
#: then a join's -- and last a door outdoors, never the entrance's on the
#: front. A WINDOW NEVER GIVES WAY: it is only priced (WINDOW_COST), so
#: dropping one cannot make a storey that will not lay lay, and it was given
#: way one by one before every join, kept given way, and seldom given back
#: (the code review's four rooms joined to each other, three asking a
#: window: the join that had to give way took all three windows with it, and
#: the storey took 33 s where 5.4 s laid it with two windows kept).
#: THE CLIMB GIVES WAY AFTER THE PLAN'S OWN WISHES (the fix round's phase 2,
#: 2026-10-19: the unseen plans' finding 4). Two ends are asked of a flight:
#: on the storey that lays it first, the end its room reaches (`way`) --
#: the core's own choice, laid both ways round (`_end_combos`), so it gives
#: way first, as before; and on a storey its flight is pinned on, the
#: other end (`end`), without which the stair cannot be climbed foot to
#: head -- given way first and priced like a turned side, both storeys of
#: the unseen hospital's main stair reached one end of it. It now gives way
#: after every stair wall, order and side, and a flight no place lets a
#: body climb turns back on itself (`STAIR_FALLBACK`, `_climb`).
RELAX_ORDER = ("way", "stair_pinned", "stair", "order", "side", "end", "landed", "join", "door")
#: ...the shared walls are given way only on the storey laid first (the
#: ground): above or below it a chain that would need one is dropped, the
#: block laid again on more ground (LOOKAHEAD_GROW), and failing that the
#: building handed to the lab's search -- never written with rooms its stair
#: or its neighbour cannot reach (the unseen merchant's house: one
#: contradictory ask, then every class given away, and the upper floor
#: written unreachable after 255 s). The manor (35 rooms, past the tier's own
#: cap) lays its first floor only with its stair halls' shared walls given
#: way, as the earth core laid it (stair_landed failing): it now runs to the
#: budget and is the lab's.
GROUND_ONLY = ("landed", "join")
#: A storey that does not lay with every ask gives its asks way ONE AT A
#: TIME, each kept given way while the next is tried -- those in a
#: contradiction found before laying first (`_conflicted`) -- for
#: RELAX_LINEAR tries; past them it is tried with every ask that may give
#: way given (the floor: if that does not lay, the storey is not laid on
#: that state), and else the fewest of its asks in order that lay it are
#: found by halving; once it lays, EVERY ask given way before the last is
#: tried back, the latest first (`_relaxed`). Each try is a whole solve of
#: the storey. (One at a time are tried first: in a narrow search the asks
#: aim its few cuts, and a storey with every ask given way may not lay
#: where one with a few does -- the unseen hospital's ground floor.) Named
#: per ask-before-limiting.
RELAX_LINEAR = 8
#: ...and what each ask given way costs the storey, so that of the ground's
#: outlines carried forward one whose storeys keep their asks wins over one
#: whose storeys hold only by giving them up. The end the storey laying a
#: flight first reaches (`way`) costs what a side does, as before; the end
#: the climb needs (`end`) what a stair that does not land costs -- a stair
#: its rooms reach and no one can climb is as unusable.
#: A door outdoors turned (`door`) costs more than a side: the lab's own
#: search turns one and says so (`layout_solver._place_doors`).
RELAX_COST = {"way": 30.0, "end": 80.0, "stair_pinned": 20.0, "stair": 20.0, "order": 20.0, "side": 30.0,
              "landed": 80.0, "join": 200.0, "door": 40.0}


class ArrangeBudget(RuntimeError):
    """The core passed ARRANGE_WORK_BUDGET laying one building: it stops,
    and the bridge lays the building with the lab's search, as it was laid
    before the core (`layout_bridge.solve_for`)."""


class _Meter:
    """The work one building's solve has done: table entries built, over the
    building (`ARRANGE_WORK_BUDGET`) and over each storey of each block
    (`NARROW_WORK`), counted where they are built (`_Storey._tick`)."""
    __slots__ = ("total", "by_storey", "budget")

    def __init__(self):
        self.total = 0
        self.by_storey = {}
        self.budget = ARRANGE_WORK_BUDGET


# ---------------------------------------------------------------- leaves

def _use_need(fx):
    """(along, across) paces a floor thing needs with its use space -- the
    sensible check's reading of `USE_SPACE`: a bed a long side free, a table
    a pace round it, else its front and back strips."""
    w, d, _h = fixture_footprint(fx)
    long_, short = max(w, d), min(w, d)
    kind = _kind(fx)
    if kind in _BEDS:
        return long_, short + 1
    if kind in _TABLES:
        return long_ + 1, short + 1
    front, back = USE_SPACE.get(kind, (1 if w * d > 1 else 0, 0))
    return long_, short + front + back


def _fits(a, b, at, w, h):
    if at in ("n", "s"):
        return a <= w and b <= h
    if at in ("e", "w"):
        return a <= h and b <= w
    return (a <= w and b <= h) or (a <= h and b <= w)


def _hall_fits(fw, fd, w, h, across=0):
    """Can a hall w x h hold a flight fw x fd as the tier lays one? A
    straight run (a flight longer than it is wide, two paces or more) keeps
    its hall as thick as the flight and lands at most LANDING_MAX paces
    along the run -- or, where `across` (below the ground, ACROSS_LANDING),
    up to that many paces beside the run too, within the one landing below.
    A short stair -- a ladder, a spiral, a U -- has no run to
    land along: its hall may grow either way by LANDING_MAX, to at most
    SHORT_LANDING more cells than the flight (the sensible check's one
    landing, max(4, half the flight))."""
    bw, bd = Leaf._hall_base(fw, fd)
    if w < bw or h < bd:
        return False
    if max(fw, fd) >= STRAIGHT_RUN and fw != fd:
        cap = fw * fd + max(SHORT_LANDING, fw * fd // 2)
        if fw > fd:
            if h == bd:
                return w - bw <= LANDING_MAX
            return h - bd <= across and w - bw <= LANDING_MAX and w * h <= cap
        if w == bw:
            return h - bd <= LANDING_MAX
        return w - bw <= across and h - bd <= LANDING_MAX and w * h <= cap
    return w - bw <= LANDING_MAX and h - bd <= LANDING_MAX and \
        w * h <= fw * fd + max(SHORT_LANDING, fw * fd // 2) and w * h >= bw * bd


_PAST = {}


def _hall_past(fw, fd, w, h, across=0):
    """The cells of a hall w x h round a flight fw x fd past the owner's cap
    (`_hall_fits`, LANDING_OVER_COST): 0 for a hall within the cap; for one
    beyond it, the cells past the largest hall the cap allows inside w x h
    -- a hall at most LANDING_OVER_CEILING times the least; None where w x h
    is no hall of that flight."""
    key = (fw, fd, w, h, across)
    got = _PAST.get(key, False)
    if got is not False:
        return got
    if _hall_fits(fw, fd, w, h, across):
        got = 0
    else:
        bw, bd = Leaf._hall_base(fw, fd)
        if w < bw or h < bd or w * h > LANDING_OVER_CEILING * bw * bd:
            got = None
        else:
            most = 0
            for w2 in range(bw, min(w, bw + LANDING_MAX + across) + 1):
                for h2 in range(bd, min(h, bd + LANDING_MAX + across) + 1):
                    if w2 * h2 > most and _hall_fits(fw, fd, w2, h2, across):
                        most = w2 * h2
            got = w * h - most
    _PAST[key] = got
    return got


def _kept(fw, fd, w, h, kw, kd):
    """Can a hall w x h above the ground round a flight fw x fd keep the
    landing of a hall kw x kd below it (KEPT_LANDING_COST) -- no larger than
    that hall, and a straight run's hall no longer than its flight? (As
    shapes only: `Leaf.abs_cost` places it.)"""
    bw, bd = Leaf._hall_base(fw, fd)
    if w < bw or h < bd or w > kw or h > kd:
        return False
    if max(fw, fd) >= STRAIGHT_RUN and fw != fd:
        return w == bw if fw > fd else h == bd
    return True


@dataclass
class Leaf:
    """One rectangle of a storey: a room of the plan, a corridor, or a stair
    hall. Its `table` prices every w x h it may take."""
    id: str
    kind: str                       # "room" | "corridor" | "hall"
    target: float = 0.0
    size_kind: str = "keep"         # "stated" | "keep" | "flex"
    ceiling: float = INF
    min_side: int = MIN_SIDE_ROOM
    needs: tuple = ()               # floor things: (along, across, at, along_plain, across_plain)
    under_roof: bool = False
    flexible: bool = False          # a purpose that takes spare floor (`FLEXIBLE`)
    need: float = 0.0               # what its things need (`room_target(stated=False)`)
    run: str | None = None          # corridor / hall: "ew" or "ns", or None when free
    flights: tuple = ()             # hall: the flight footprints (w, d) it may take
    pin: Rect | None = None         # hall: its flight, where a storey laid already put it
    landing: bool = True            # a pinned hall may land past its flight
    across: int = 0                 # ...and beside it, this deep (below the ground, ACROSS_LANDING)
    shaft: str | None = None
    hint: float = 0.0               # area, for balancing cuts
    min_landing: int = 0            # hall: landing along the run a window above asks (WINDOW_LANDING_COST)
    dug: bool = False               # a room of a dug storey: no band under its target (`_size_cost`)
    over: bool = False              # hall of a storey wholly floor: a landing past the cap, priced (LANDING_OVER_COST)
    used_end: int = 0               # pinned hall: the end its storey takes (DEAD_LANDING_COST beyond the other)
    keep: Rect | None = None        # pinned hall above the ground: its hall below, whose landing it may keep
    whole: bool = False             # ...and must keep whole (a storey of one room, KEPT_LANDING_COST)

    # -- relative shape cost --------------------------------------------------

    def cost(self, w, h):
        if self.kind == "hall":
            return self._hall_cost(w, h)
        lo, hi = (w, h) if w <= h else (h, w)
        if self.kind == "corridor":
            if lo != CORRIDOR_WIDTH or hi < CORRIDOR_MIN_LENGTH:
                return INF
            if self.run == "ns" and w != CORRIDOR_WIDTH:
                return INF
            if self.run == "ew" and h != CORRIDOR_WIDTH:
                return INF
            c = CORRIDOR_LENGTH_COST * hi
            if self.target > 0:
                c += CORRIDOR_SIZE_W * abs(math.log(w * h / self.target))
            return c
        if lo < self.min_side:
            return INF
        ar = hi / lo
        if ar > ASPECT_MAX:
            return INF
        c = THIN_COST if lo == 2 else 0.0
        if ar > ASPECT_FREE:
            c += ASPECT_COST * (min(ar, ASPECT_SOFT) - ASPECT_FREE)
            if ar > ASPECT_SOFT:
                c += ASPECT_STEEP * (ar - ASPECT_SOFT)
        c += self._size_cost(w * h)
        if self.needs:
            fit = 0.0
            for a, b, at, ap, bp in self.needs:
                if not _fits(a, b, at, w, h):
                    fit += FIT_PLAIN_COST if _fits(ap, bp, at, w, h) else FIT_COST
                if self.under_roof and not (a <= hi and b <= lo) and not (ap <= hi and bp <= lo):
                    fit += DEEP_COST
            c += min(fit, FIT_CAP)
        return c

    def _size_cost(self, area):
        t = self.target
        if t <= 0:
            return 0.0
        d = math.log(area / t)
        # A ROOM OF A DUG STOREY TAKES WHAT IT NEEDS: no outline makes it
        # smaller, so under its target its band is only its slack (a row of
        # a small room, whole paces cannot hit a target exactly) -- earth
        # beside it is never bought by shrinking it (the lab's run 3: a
        # basement 16% short of its target, to save the earth and the
        # UNDER_COST of the three columns it would have taken)
        floor_band = self.dug and d < 0
        if self.size_kind == "stated":
            allow = math.log(1.0 + (STATED_SLACK / t if floor_band else max(STATED_BAND, STATED_SLACK / t)))
            out = W_STATED_OUT
            if d > 0 and self.flexible:
                # SPARE FLOOR GOES TO A ROOM THAT MAY TAKE IT (the owner's
                # default, 2026-10-15): a stated room of a flexible purpose
                # grows past its band more cheaply than a service room does,
                # and more cheaply still toward what its things need. (Laid
                # as one rectangle wholly floor it did not take the floor a
                # small genkan was given: on the shrine's clone 174 #2, a
                # genkan stated at 3 m2 came out 350% past it and the main
                # hall 10% short -- the review's visual 2. Spare floor a room
                # needs no part of is a notch since 2026-10-19, NOTCH_COST.)
                out = W_STATED_OUT_FLEX if area <= self.need else W_STATED_OUT_FLEX_PAST
            return W_STATED * abs(d) + out * max(0.0, abs(d) - allow)
        if self.size_kind == "keep" or d < 0:
            allow = math.log(1.0 + (KEEP_SLACK / t if floor_band else max(KEEP_BAND, KEEP_SLACK / t)))
            return W_KEEP * abs(d) + W_KEEP_OUT * max(0.0, abs(d) - allow)
        grow = math.log(1.0 + GROW_BAND)
        c = W_GROW * min(d, grow) + W_GROW_MID * max(0.0, d - grow)
        if area > self.ceiling:
            c += W_CEILING * math.log(area / self.ceiling)
        return c

    def _hall_cost(self, w, h):
        best = INF
        for fw, fd in self.flights:
            past = _hall_past(fw, fd, w, h, self.across) if self.over else \
                (0 if _hall_fits(fw, fd, w, h, self.across) else None)
            if past is not None:
                bw, bd = self._hall_base(fw, fd)
                c = LANDING_COST * (w * h - bw * bd) + LANDING_OVER_COST * past
                if self.min_landing:
                    along = w - bw if fw > fd else (h - bd if fd > fw else 0)
                    c += WINDOW_LANDING_COST * max(0, self.min_landing - along)
                best = min(best, c)
            if self.keep is not None and _kept(fw, fd, w, h, self.keep.w, self.keep.d):
                # a pinned hall above the ground keeping its landing below
                # (KEPT_LANDING_COST): its shapes, for the bound
                bw, bd = self._hall_base(fw, fd)
                best = min(best, KEPT_LANDING_COST * (w * h - bw * bd))
        return best

    @staticmethod
    def _hall_base(fw, fd):
        """The least hall round a flight: the flight, at least
        HALL_MIN_ACROSS across its run."""
        if fw > fd:
            return fw, max(fd, HALL_MIN_ACROSS)
        if fd > fw:
            return max(fw, HALL_MIN_ACROSS), fd
        return max(fw, HALL_MIN_ACROSS), max(fd, HALL_MIN_ACROSS)

    # -- a pinned hall ---------------------------------------------------------

    def abs_cost(self, x, y, w, h):
        """A hall whose flight a storey laid already put at `pin`: the hall
        holds the flight, as thick as its least hall, at most LANDING_MAX
        longer along the run."""
        f = self.pin
        if not (x <= f.x and y <= f.y and x + w >= f.x + f.w and y + h >= f.y + f.d):
            return INF
        bw, bd = self._hall_base(f.w, f.d)
        if not self.landing:
            # ABOVE THE GROUND: the flight's least hall, or the landing its
            # hall below took beside the run (KEPT_LANDING_COST) -- on a
            # storey of one room, that landing whole
            k = self.keep
            run = max(f.w, f.d) >= STRAIGHT_RUN and f.w != f.d
            if self.whole and k is not None:
                full = (Rect(f.x, k.y, f.w, k.d) if run and f.w > f.d else
                        Rect(k.x, f.y, k.w, f.d) if run else k)
                if (x, y, w, h) != (full.x, full.y, full.w, full.d) or w < bw or h < bd:
                    return INF
                return KEPT_LANDING_COST * (w * h - bw * bd)
            if w * h == bw * bd and _hall_fits(f.w, f.d, w, h):
                return 0.0
            if k is None or not (k.x <= x and k.y <= y and x + w <= k.x + k.w and y + h <= k.y + k.d):
                return INF
            if run and f.w > f.d and (x != f.x or w != f.w):
                return INF
            if run and f.d > f.w and (y != f.y or h != f.d):
                return INF
            if w < bw or h < bd:
                return INF
            return KEPT_LANDING_COST * (w * h - bw * bd)
        if not _hall_fits(f.w, f.d, w, h, self.across):
            return INF
        c = LANDING_COST * (w * h - bw * bd)
        if self.used_end and max(f.w, f.d) >= STRAIGHT_RUN and f.w != f.d:
            # A LANDING PAST THE END ITS STOREY DOES NOT TAKE (DEAD_LANDING_
            # COST): cells beyond the flight's other end, the hall's whole
            # depth there
            if f.w > f.d:
                past = (x + w - f.x - f.w) if self.used_end == 8 else (f.x - x) if self.used_end == 2 else 0
                c += DEAD_LANDING_COST * max(0, past) * h
            else:
                past = (y + h - f.y - f.d) if self.used_end == 1 else (f.y - y) if self.used_end == 4 else 0
                c += DEAD_LANDING_COST * max(0, past) * w
        return c


# ---------------------------------------------------------------- one storey

class _Table:
    """A node's shape function: {(w, h, key): cost}, with how each entry was
    laid (`back`). `key` holds the extents of the leaves an ancestor's
    coupled cut must check (`_Storey.etable`); () for a plain table. Its
    entries grouped by the side two parts share serve the convolutions
    (`grouped`)."""
    __slots__ = ("cost", "back", "best", "_grouped", "_at")

    def __init__(self):
        self.cost = {}
        self.back = {}
        self._grouped = {}
        self._at = None
        self.best = INF

    def put(self, key, c, how):
        if c < self.cost.get(key, INF):
            self.cost[key] = c
            self.back[key] = how

    def get(self, w, h):
        return self.cost.get((w, h, ()), INF)

    def at(self, w, h):
        """[(key, cost)] of every entry of shape w x h."""
        if self._at is None:
            d = {}
            for (ww, hh, k), c in self.cost.items():
                d.setdefault((ww, hh), []).append((k, c))
            self._at = d
        return self._at.get((w, h), ())

    def seal(self):
        if self.cost:
            self.best = min(self.cost.values())
            cap = self.best + PRUNE_MARGIN
            for k in [k for k, c in self.cost.items() if c > cap]:
                del self.cost[k]
                del self.back[k]
            keyed = {}
            for (w, h, k), c in self.cost.items():
                if k:
                    keyed.setdefault((w, h), []).append((c, k))
            for (w, h), lst in keyed.items():
                if len(lst) > KEY_CAP:
                    lst.sort()
                    for _c, k in lst[KEY_CAP:]:
                        del self.cost[(w, h, k)]
                        del self.back[(w, h, k)]

    def grouped(self, axis):
        """{shared side: [(own side, [(cost, key)...] cheapest first)...]}
        with own sides ascending: heights shared for a west|east cut."""
        got = self._grouped.get(axis)
        if got is None:
            d = {}
            for (w, h, k), c in self.cost.items():
                shared, own = (h, w) if axis == "v" else (w, h)
                d.setdefault(shared, {}).setdefault(own, []).append((c, k))
            got = {}
            for shared, by_own in d.items():
                got[shared] = [(own, sorted(by_own[own])) for own in sorted(by_own)]
            self._grouped[axis] = got
        return got

class _Storey:
    """One storey's layout problem and its DP.

    `leaves` [Leaf], indexed by position. `orient` {(i, j): side bit}: leaf j
    lies on leaf i's side (both ways round). `adj` [(i, j)]: pairs that share
    a wall. `demand` {i: mask}: the outline sides a leaf must reach (a door
    outdoors, the entrance on the front, a block beyond). `wish` {i: mask}:
    sides a window asks; `wish_any`: leaves that open outdoors on no named
    side; `need` {(i, side bit): n}: the cells of outside wall the side's
    windows and doors take, one each. `hall_end` {i: side bit}: the end of
    its flight a hall's room must reach on this storey. `pad`: the cost of a roof cell, or None where a
    storey is one rectangle wholly floor (the ground). `earth`: the storey
    is dug (below the ground), its strips earth at `pad` a cell (EARTH_COST).
    `M`: the largest side tried. `serves` {hall: [rooms it opens onto here]}."""

    def __init__(self, leaves, orient, adj, demand, wish, wish_any, hall_end, pad, M, serves, narrow=False,
                 need=None, cave=None, cave_any=None, earth=False, meter=None, level_key=None, over=None,
                 notch=frozenset(), heart=frozenset()):
        self.leaves = leaves
        # the ground, its outline free to step (`NOTCH_COST`) in the slots of
        # the leaves `notch` names, and the heart rooms that keep a wall to
        # the outside (`HEART_DARK_COST`)
        self.notch = bool(notch)
        self.notch_at = frozenset(notch)
        self.heart = heart
        self.doors = {}                 # {leaf: outline sides it reaches for a door outdoors only}
        self.step_cost = NOTCH_STEP_COST  # each reflex corner a notch makes (`lay_free`'s retry)
        # a full storey above the ground prices a ledge of roof along a whole
        # outer wall (`LEDGE_COST`)
        self.ledge = LEDGE_COST if pad == PAD_UPPER and not earth else 0.0
        # {leaf: [Rect]}: the rooms below an upper room's stair joins, which
        # it stands over where it can (OVER_COST) -- read on the absolute
        # extents, so a set holding one is laid as a set holding a pin is
        self.over = over or {}
        # the building's count of table entries (`_Meter`), and the storey
        # this problem is one try of (NARROW_WORK is counted per storey)
        self.meter = meter
        self.level_key = level_key
        self.earth = earth
        self.need = need or {}
        # a cavern's asked side ({leaf: side bits}, priced CAVE_SIDE_COST
        # when cut off the outline) and the rooms a cavern opens from
        # (CAVE_ANY_COST left wholly inside)
        self.cave = cave or {}
        self.cave_any = cave_any or set()
        self.n = len(leaves)
        self.orient = orient
        self.adj = adj
        self.demand = demand
        self.wish = wish
        self.wish_any = wish_any
        self.hall_end = hall_end
        self.pad = pad
        self.M = M
        self.serves = serves
        self.full = (1 << self.n) - 1
        self.pinned = 0
        for i, lf in enumerate(leaves):
            if lf.pin is not None:
                self.pinned |= 1 << i
        self.absmask = self.pinned
        for i in self.over:
            self.absmask |= 1 << i
        # onside[i][bit]: the leaves lying on leaf i's side `bit`
        self.onside = [{b: 0 for b in (1, 2, 4, 8)} for _ in range(self.n)]
        for (i, j), b in orient.items():
            self.onside[i][b] |= 1 << j
        self.adj_of = [0] * self.n
        for i, j in adj:
            self.adj_of[i] |= 1 << j
            self.adj_of[j] |= 1 << i
        self.hint = [max(1.0, lf.hint) for lf in leaves]
        # A LARGE STOREY (the manor's ground floor: twelve rooms and three
        # stair halls) is searched over fewer cuts per set of leaves, so the
        # exact search stays within the tier's time
        large = self.n > LARGE_STOREY or narrow
        self.narrowed = large
        # a join between two rooms asked no side (NARROW_WORK_OPEN)
        self.open_joins = sum(1 for i, j in adj if (i, j) not in orient
                              and leaves[i].kind != "hall" and leaves[j].kind != "hall")
        self.narrow_at = NARROW_WORK_OPEN if self.open_joins else NARROW_WORK
        self.cut_cap = CUT_CAP_LARGE if large else CUT_CAP
        self.variant_cap = VARIANT_CAP_LARGE if large else VARIANT_CAP
        self.downset_limit = DOWNSET_LIMIT_LARGE if large else DOWNSET_LIMIT
        # EVERY JOIN READ BY ITS EXTENTS, none by the span / same-end rules,
        # on a large storey: searched over few cuts and one variant each, a
        # rule chosen first there (a room made to span its part) piles touch
        # demands until a set of leaves must reach all four sides of its part
        # (the manor's ground floor: no layout at all until every join gave
        # way); the exact reading over-constrains nothing
        self.couple_all = large
        self.work = 0                   # table entries built (`_Building.work`)
        self.leaf_margin = LEAF_MARGIN_LARGE if large else LEAF_MARGIN
        self.key_cap = KEY_CAP_LARGE if large else KEY_CAP
        self._tables = {}
        self._cuts = {}
        self._leaf_tables = {}
        self._g = {}
        self._gcore = {}
        self._halls = {}
        self._splits = {}               # this storey's own: a coupled check reads its pins (`_check`)
        self._ek = {}                   # this storey's own: S -> the hall ends its tables read (`_ends_of`)
        self._dk = {}                   # ...and S -> the asks given way its tables read (`_drops_of`)
        self.drop_masks = ()            # (key, both leaves, hall) of each ask given way (`_Building.make`)

    # -- the work done ----------------------------------------------------------

    def _tick(self, n):
        """Count `n` table entries built (`_Meter`): past ARRANGE_WORK_BUDGET
        over the building the solve stops (`ArrangeBudget`); past NARROW_WORK
        over this storey it lays on narrowly, from here (`_narrow`)."""
        self.work += n
        m = self.meter
        if m is None:
            return
        m.total += n
        k = m.by_storey[self.level_key] = m.by_storey.get(self.level_key, 0) + n
        if m.total > m.budget:
            raise ArrangeBudget(f"{m.total} table entries built, past the core's budget of {m.budget}")
        if k > self.narrow_at and not self.narrowed:
            self._narrow()

    def _narrow(self):
        """LAY ON AS A LARGE STOREY IS LAID, MID-SOLVE (NARROW_WORK): fewer
        cuts a set of leaves, one variant each, every join read by its
        extents. The tables built already stand -- each entry is a way of
        laying its leaves, however searched -- so nothing is undone."""
        self.narrowed = True
        self.cut_cap = CUT_CAP_LARGE
        self.variant_cap = VARIANT_CAP_LARGE
        self.downset_limit = DOWNSET_LIMIT_LARGE
        self.couple_all = True
        self.leaf_margin = LEAF_MARGIN_LARGE
        self.key_cap = KEY_CAP_LARGE

    def _ends_of(self, S):
        """The ends asked of the halls of S whose served room is in S too --
        all a table of S reads of `hall_end` (`_cross`, `_loose_pair`) -- so
        the tables of one storey laid each way round its flights are shared
        wherever a set holds no hall with its room (`_Building.make`): the
        ground was solved from scratch for each way round, nothing shared
        (the code review's finding 13, the unseen inn's four ways round: 48
        of its 53 s)."""
        got = self._ek.get(S)
        if got is None:
            got = tuple((h, e) for h, e in sorted(self.hall_end.items())
                        if S >> h & 1 and any(S >> r & 1 for r in self.serves.get(h, ())))
            self._ek[S] = got
        return got

    def _drops_of(self, S):
        """The asks given way that a table of S reads: a join or a side
        between two of its leaves, and a stair's wall given way by a hall of
        S (its flight's shape reads it, `_Building._hall_leaf`). With these
        in the key, the tries of one storey with different asks given way
        share every table no ask given way touches (`_Building.make`): each
        try was a solve from scratch (the unseen farmhouse's upper floor,
        four tries on each of three carried states, 1.5 to 3 s a try)."""
        got = self._dk.get(S)
        if got is None:
            got = tuple(k for k, both, hall in self.drop_masks if S & both == both or S & hall)
            self._dk[S] = got
        return got

    def _sig(self, S):
        """What a table of S reads beyond S itself and its T, O and Q: the
        ends asked of its halls (`_ends_of`) and the asks given way among its
        leaves (`_drops_of`)."""
        return self._ends_of(S), self._drops_of(S)

    def _read(self, cuts):
        """The indices of `cuts` (one set's list, `cuts()`) a table reads: all
        of them -- but on a storey gone narrow mid-solve (`_narrow`), the
        first `cut_cap` bipartitions an axis and `variant_cap` variants each,
        as `cuts()` lists them for a storey narrow from the start: the list a
        set got before the switch is kept whole (its indices are how its
        table's entries were laid), and read narrowly from then on."""
        if not self.narrowed:
            return range(len(cuts))
        out, per = [], {}
        for ci, cut in enumerate(cuts):
            seen = per.setdefault(cut[0], {})
            n = seen.get(cut[1])
            if n is None and len(seen) >= self.cut_cap or n is not None and n >= self.variant_cap:
                continue
            seen[cut[1]] = (n or 0) + 1
            out.append(ci)
        return out

    # -- helpers -------------------------------------------------------------

    def members(self, S):
        return [i for i in range(self.n) if S >> i & 1]

    @staticmethod
    def canon(t):
        """A touch-demand dict as the tuple the tables are keyed by."""
        return tuple(sorted((i, m) for i, m in t.items() if m))

    def feasible(self, P, t):
        """Medjdoub's reduction: a leaf that must reach side X of its part has
        no leaf of the part on its side X."""
        for i, m in t.items():
            if not m or not P >> i & 1:
                continue
            for b in (1, 2, 4, 8):
                if m & b and self.onside[i][b] & P & ~(1 << i):
                    return False
        return True

    def spanable(self, i, axis):
        lf = self.leaves[i]
        if lf.kind == "room":
            return True
        if lf.kind == "corridor":
            return lf.run in (None, "ns" if axis == "v" else "ew")
        return False

    def _run_of(self, i):
        lf = self.leaves[i]
        if lf.pin is not None:
            return "ew" if lf.pin.w > lf.pin.d else ("ns" if lf.pin.d > lf.pin.w else None)
        return lf.run

    # -- the cuts of a set of leaves -----------------------------------------

    def cuts(self, S, T, capped=True):
        """Every bipartition of S by one cut the relations allow, with the
        touch demands its two parts inherit and the joins whose shared wall
        the cut must check by their extents: [(axis, A, tA, B, tB, loose)];
        at most `cut_cap` bipartitions an axis unless `capped` is false."""
        key = (S, T, capped, self._sig(S))
        got = self._cuts.get(key)
        if got is not None:
            return got
        out = []
        mem = self.members(S)
        Td = dict(T)
        for axis in ("v", "h"):
            first, second = (8, 2) if axis == "v" else (1, 4)
            cross = _NS if axis == "v" else _EW
            parent = {i: i for i in mem}

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for (i, j), b in self.orient.items():
                if i < j and S >> i & 1 and S >> j & 1 and b & cross:
                    ri, rj = find(i), find(j)
                    if ri != rj:
                        parent[max(ri, rj)] = min(ri, rj)
            atoms = {}
            for i in mem:
                atoms.setdefault(find(i), []).append(i)
            if len(atoms) < 2:
                continue
            roots = sorted(atoms)
            idx = {r: k for k, r in enumerate(roots)}
            amask = [sum(1 << i for i in atoms[r]) for r in roots]
            succ = [set() for _ in roots]
            for (i, j), b in self.orient.items():
                if not (S >> i & 1 and S >> j & 1):
                    continue
                ai, aj = idx[find(i)], idx[find(j)]
                if ai != aj and b == second:
                    succ[ai].add(aj)
            dk = ("dsets", S, axis, self.downset_limit, self._sig(S)[1])
            downsets = self._tables.get(dk, False)
            if downsets is False:
                # the down-sets of S on this axis read only the side order,
                # the joins and the leaves' areas: one list for every T
                downsets = self._tables[dk] = self._downsets(len(roots), succ, amask, S)
            if downsets is None:
                continue                      # the side order has a cycle on this axis
            # the most balanced bipartitions first, until `cut_cap` of them
            # hold (a cap counted before the touch demands are read left a
            # large storey with none)
            taken = 0
            for A in downsets:
                if capped and taken >= self.cut_cap:
                    break
                B = S & ~A
                if any(Td.get(i, 0) & second for i in self.members(A)):
                    continue
                if any(Td.get(i, 0) & first for i in self.members(B)):
                    continue
                got = self._cross(A, B, axis, Td)
                for tA, tB, loose in got:
                    out.append((axis, A, tA, B, tB, loose))
                taken += bool(got)
        self._cuts[key] = out
        return out

    def _downsets(self, k, succ, amask, S):
        """The sets of atoms closed under 'lies west / north of' (the A side
        of a cut), neither empty nor all; None when the order has a cycle.
        EVERY ONE where there are at most DOWNSET_EXACT_ATOMS atoms, else
        those grown from each atom (`_grown`) -- RANKED BEFORE ANY IS LEFT
        OUT: the fewest joined pairs across the cut, then the most balanced,
        and the best `downset_limit` kept."""
        pred = [set() for _ in range(k)]
        for a in range(k):
            for b in succ[a]:
                pred[b].add(a)
        indeg = [len(p) for p in pred]
        order, ready = [], [a for a in range(k) if indeg[a] == 0]
        while ready:
            a = ready.pop(0)
            order.append(a)
            for b in sorted(succ[a]):
                indeg[b] -= 1
                if indeg[b] == 0:
                    ready.append(b)
        if len(order) < k:
            return None
        if k <= DOWNSET_EXACT_ATOMS:
            found = []

            def walk(pos, chosen, mask):
                if pos == k:
                    if mask and mask != S:
                        found.append(mask)
                    return
                a = order[pos]
                walk(pos + 1, chosen, mask)
                if pred[a] <= chosen:
                    walk(pos + 1, chosen | {a}, mask | amask[a])

            walk(0, frozenset(), 0)
        else:
            found = self._grown(k, pred, order, amask, S)
        total = sum(self.hint[i] for i in self.members(S))

        def rank(A):
            # the cuts that part the fewest joined pairs first -- each pair
            # across a cut is a wall the cut must keep -- then the most
            # balanced (on a large storey only the first few are read); an
            # exact tie falls to the leaves' order
            share = sum(self.hint[i] for i in self.members(A)) / total
            crossing = sum(bin(self.adj_of[i] & S & ~A).count("1") for i in self.members(A))
            return (crossing, abs(share - 0.5), A)

        found.sort(key=rank)
        return found[:self.downset_limit]

    def _grown(self, k, pred, order, amask, S):
        """The down-sets of a set of many atoms (past DOWNSET_EXACT_ATOMS):
        from each atom, the least down-set holding it (it and every atom that
        must lie west or north of it), grown one atom at a time -- an atom
        whose own predecessors are in -- by the atom that leaves the fewest
        joined pairs across, then the smaller; every set on the way kept. A
        cut that parts few joined pairs is a run of joined rooms, which this
        reaches from wherever it starts."""
        anc = [frozenset()] * k
        for a in order:
            s = set(pred[a])
            for p in pred[a]:
                s |= anc[p]
            anc[a] = frozenset(s)
        found = set()
        for start in range(k):
            chosen = set(anc[start]) | {start}
            mask = 0
            for a in chosen:
                mask |= amask[a]
            while True:
                if mask and mask != S:
                    found.add(mask)
                cand = [a for a in range(k) if a not in chosen and pred[a] <= chosen]
                if not cand:
                    break

                def grow(a, mask=mask):
                    m2 = mask | amask[a]
                    across = sum(bin(self.adj_of[i] & S & ~m2).count("1") for i in self.members(m2))
                    return (across, sum(self.hint[i] for i in self.members(amask[a])), a)

                a = min(cand, key=grow)
                chosen.add(a)
                mask |= amask[a]
        return sorted(found)

    def _cross(self, A, B, axis, T):
        """The touch demands a cut puts on its two parts, as variants
        [(tA, tB, loose)]. Every join across the cut makes the cut one of its
        walls; so that the two share a wall whatever the sizes, one room of
        each joined group spans its part along the cut, or a single pair
        keeps the same end of it. A group no such rule holds -- a room under
        two stair halls side by side, the shrine's main hall -- is COUPLED:
        its pairs go in `loose` as (a, b, least overlap, end), and the DP
        checks their extents (`etable`). A stair hall's room keeps the end of
        the flight its storey is reached by (`hall_end`). [] when no variant
        keeps both parts feasible."""
        first, second = (8, 2) if axis == "v" else (1, 4)
        ends = (1, 4) if axis == "v" else (8, 2)
        tA = {i: T.get(i, 0) for i in self.members(A)}
        tB = {i: T.get(i, 0) for i in self.members(B)}
        pairs = []
        for i in tA:
            m = self.adj_of[i] & B
            for j in range(self.n):
                if m >> j & 1:
                    pairs.append((i, j))
                    tA[i] |= second
                    tB[j] |= first
        if not self.feasible(A, tA) or not self.feasible(B, tB):
            return []
        if not pairs:
            return [(self.canon(tA), self.canon(tB), ())]
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i, j in pairs:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)
        groups = {}
        for i, j in pairs:
            groups.setdefault(find(i), []).append((i, j))
        group_opts = []
        for g in sorted(groups):
            gp = groups[g]
            ca = sorted({i for i, _ in gp})
            cb = sorted({j for _, j in gp})
            opts = []
            if len(ca) == 1 and self.spanable(ca[0], axis):
                opts.append(((ca[0], ends[0] | ends[1]),))
            if len(cb) == 1 and self.spanable(cb[0], axis):
                opts.append(((cb[0], ends[0] | ends[1]),))
            if len(ca) == 1 and len(cb) == 1:
                for e in ends:
                    opts.append(((ca[0], e), (cb[0], e)))
            loose = []
            ok = True
            across = False
            for i, j in gp:
                pair_end = 0
                need = self._min_shared(i, j)
                for h, r, h_in_a in ((i, j, True), (j, i, False)):
                    if self.leaves[h].kind != "hall" or r not in self.serves.get(h, ()):
                        continue
                    run = self._run_of(h)
                    want = self.hall_end.get(h, 0)
                    if run is None:
                        continue
                    parallel = (axis == "h") == (run == "ew")
                    if not parallel:
                        # the room stands at an end of the flight: that end
                        # -- or, a pinned flight below the ground, the other
                        # with a landing beside the run between (ACROSS_
                        # LANDING), read on the extents (`_chk_cost`)
                        facing = second if h_in_a else first
                        if want and want != facing:
                            if self.leaves[h].across and self.leaves[h].pin is not None:
                                pair_end = ACROSS_END
                                across = True
                            else:
                                ok = False
                        continue
                    # a stair hall and the room it serves: the room reaches
                    # the end of the flight this storey takes
                    pair_end = want or ALL_ENDS
                    need = ALONG_SHARED
                    keep = []
                    for opt in opts:
                        adds = dict(opt)
                        if r in adds and adds[r] == ends[0] | ends[1]:
                            keep.append(opt)              # the room spans: every end
                        elif h in adds and r in adds and adds[h] == adds[r] and \
                                (not want or adds[r] == want):
                            keep.append(opt)              # the same end, the end asked
                    opts = keep
                loose.append((i, j, need, pair_end))
            if not ok:
                return []
            # an option that leaves either part unable to keep its demands is
            # no option: where none is left the group is coupled
            fit = []
            for opt in opts:
                nA, nB = dict(tA), dict(tB)
                for i, m in opt:
                    if i in nA:
                        nA[i] |= m
                    else:
                        nB[i] |= m
                if self.feasible(A, nA) and self.feasible(B, nB):
                    fit.append(opt)
            # A JOIN ASKED NO SIDE IS READ ONE WAY: adjacent on any side, its
            # shared wall checked on the extents. Read as touch variants --
            # either room spans, or both keep one end -- each unsided join
            # across each of the many cuts no side rules out multiplied the
            # tables (the code review's finding 3: six rooms joined with no
            # side asked, 6,124 tables and 1 GB, 46 s, one try; eight, past
            # 1.6 GB), where the plan said no more than 'they share a wall'
            unsided = all((i, j) not in self.orient and self.leaves[i].kind != "hall"
                          and self.leaves[j].kind != "hall" for i, j in gp)
            if not fit or self.couple_all or across or unsided:
                group_opts.append([("loose", tuple(loose))])
            elif self.pinned and any(self.leaves[x].kind == "hall" for x in ca + cb):
                # on a storey with a flight pinned where a storey laid
                # already put it, a stair hall seldom stands where the span
                # or same-end rule would put it: its room is offered the
                # exact reading too
                group_opts.append(fit + [("loose", tuple(loose))])
            else:
                group_opts.append(fit)
        variants = [((), ())]
        for opts in group_opts:
            nxt = []
            for adds, loose in variants:
                for opt in opts:
                    if opt and opt[0] == "loose":
                        nxt.append((adds, loose + opt[1]))
                    else:
                        nxt.append((adds + opt, loose))
            variants = nxt[:self.variant_cap * 4]
        out = []
        for adds, loose in variants:
            nA, nB = dict(tA), dict(tB)
            for i, m in adds:
                if i in nA:
                    nA[i] |= m
                else:
                    nB[i] |= m
            if self.feasible(A, nA) and self.feasible(B, nB):
                out.append((self.canon(nA), self.canon(nB), loose))
            if len(out) >= self.variant_cap:
                break
        if not out:
            # the groups' rules clash with each other: every group coupled
            every = tuple(p for opts in group_opts for opt in opts[:1] if opt and opt[0] == "loose"
                          for p in opt[1])
            if len(every) == len(pairs):
                return []
            loose_all = []
            for g in sorted(groups):
                for i, j in groups[g]:
                    loose_all.append(self._loose_pair(i, j, axis))
            out.append((self.canon(tA), self.canon(tB), tuple(loose_all)))
        return out

    def _loose_pair(self, i, j, axis):
        """(i, j, least overlap, end) for a coupled join across a cut (i of
        its west or north part)."""
        first, second = (8, 2) if axis == "v" else (1, 4)
        for h, r in ((i, j), (j, i)):
            if self.leaves[h].kind == "hall" and r in self.serves.get(h, ()):
                run = self._run_of(h)
                if run is not None and (axis == "h") == (run == "ew"):
                    return (i, j, ALONG_SHARED, self.hall_end.get(h, 0) or ALL_ENDS)
                want = self.hall_end.get(h, 0)
                if run is not None and want and want != (second if h == i else first) and \
                        self.leaves[h].across and self.leaves[h].pin is not None:
                    return (i, j, self._min_shared(i, j), ACROSS_END)
        return (i, j, self._min_shared(i, j), 0)

    def _min_shared(self, i, j):
        """The least wall a coupled join keeps: MIN_SHARED, but one pace
        where either is a corridor -- its two-pace end holds a doorway to
        each of two rooms (the manor's cellar passage: two rooms off its
        south end, none laid while each asked two paces). A ROOM BESIDE A
        CORRIDOR WHOSE FLIGHT ARRIVES AT THE CORRIDOR'S END (`_flight_at_end`)
        WANTS MIN_SHARED, AT A PRICE: -MIN_SHARED, one pace held and each
        coupled cut charging HEAD_SHARED_COST where it meets fewer
        (`_chk_cost`). A room meeting the corridor by one pace met it at the
        corner cell the stair's doorway opens from, two doorways from one
        cell (the review's visual 5, 8 of 18 shrine layouts); held as a rule
        (the fix round's phase 2) it made the lab's runs 2 and 3 lay their
        main hall 41% past its stated size to give the meditation room its
        two paces. Two doorways beside one corner are better than a hall that
        size (the owner, phase 3)."""
        for c, r in ((i, j), (j, i)):
            if self.leaves[c].kind == "corridor" and self.leaves[r].kind == "room":
                if self._flight_at_end(c) and self.orient.get((c, r), 0) not in self._ends_of_run(c):
                    return -MIN_SHARED
                return 1
        if self.leaves[i].kind == "corridor" or self.leaves[j].kind == "corridor":
            return 1
        return MIN_SHARED

    def _ends_of_run(self, c):
        """The side bits of a corridor's two ends: () where it runs free."""
        run = self._run_of(c)
        return (1, 4) if run == "ns" else (8, 2) if run == "ew" else ()

    def _flight_at_end(self, c):
        """Does a stair hall that serves corridor `c` stand at one of its
        ends, as the plan asks it (the side the stair's wall gives)?"""
        ends = self._ends_of_run(c)
        return any(self.leaves[h].kind == "hall" and c in rooms and self.orient.get((c, h), 0) in ends
                   for h, rooms in self.serves.items()) if ends else False

    # -- wishes ----------------------------------------------------------------

    def leaf_extra(self, i, O):
        """A room that opens outdoors on no named side, or that a cavern
        opens from, left wholly inside. (A window's side, and a cavern's, is
        charged at the cut that takes it, `_wins`.)"""
        c = 0.0
        if not O:
            if i in self.wish_any:
                c += OUTWARD_ANY_COST
            if i in self.cave_any:
                c += CAVE_ANY_COST
            if i in self.heart:
                c += HEART_DARK_COST
        return c

    def _wins(self, A, B, axis, O):
        """What a cut costs the windows it takes: WINDOW_COST for each leaf
        whose window side the cut makes a wall inside the storey -- its part's
        side that was on the outline. Where the part across is one stair hall
        alone, the window can still look out over the roof beside the hall if
        the room runs past the hall's end: those (leaf, hall) pairs are
        returned to be read on their extents (the roof room's south gable
        window, beside the stair that climbs to its south wall)."""
        first, second = (8, 2) if axis == "v" else (1, 4)
        cost, pairs = 0.0, []
        for part, other, side in ((A, B, second), (B, A, first)):
            if not O & side:
                continue
            lone = self.members(other)
            hall = lone[0] if len(lone) == 1 and self.leaves[lone[0]].kind == "hall" else None
            for i in self.members(part):
                if self.wish.get(i, 0) & side:
                    cost += WINDOW_COST
                    if hall is not None:
                        pairs.append((i, hall, self.need.get((i, side), 1)))
                if self.cave.get(i, 0) & side:
                    cost += CAVE_SIDE_COST
        return cost, pairs

    def _split(self, cut, Q, O):
        """What combining one cut needs: (axis, A, tA, OA, B, tB, OB, QA, QB,
        chk, wcost, wchk) -- the parts, their touch demands and outline
        sides, the extents each part reports (Q's own, the coupled joins',
        the windows'), the coupled checks and the windows' charge. Read
        once a cut: the pinned DP asks it again for every place of the cut
        (a dug storey's earth makes many places worth reading)."""
        mk = (cut, Q, O)
        got = self._splits.get(mk)
        if got is not None:
            return got
        axis, A, tA, B, tB, loose = cut
        first, second = (8, 2) if axis == "v" else (1, 4)
        ax = 1 if axis == "v" else 0
        wcost, wpairs = self._wins(A, B, axis, O)
        qa = {q for q in Q if A >> q[0] & 1} | {(a, ax) for a, _b, _n, _e in loose}
        qb = {q for q in Q if B >> q[0] & 1} | {(b, ax) for _a, b, _n, _e in loose}
        for lf, hall, _n in wpairs:
            for i in (lf, hall):
                (qa if A >> i & 1 else qb).add((i, ax))
        QA, QB = tuple(sorted(qa)), tuple(sorted(qb))
        chk = self._check(loose, QA, QB, ax) if loose else ()
        wchk = [(A >> lf & 1, (QA if A >> lf & 1 else QB).index((lf, ax)),
                 (QA if A >> hall & 1 else QB).index((hall, ax)), n) for lf, hall, n in wpairs]
        if self.notch and self.heart:
            # A DARK HEART ROOM ALONE ACROSS THE CUT FROM ONE GROUND ROOM: a
            # notch that room runs from the outline along the cut meets the
            # heart's wall (`_notched` takes back HEART_DARK_COST)
            lit = LIT_EW if axis == "h" else LIT_NS
            for P, OP, X, tX, is_a in ((A, O & ~second, B, tB, False), (B, O & ~first, A, tA, True)):
                if P & (P - 1) or X & (X - 1) or OP:
                    continue
                h, x = P.bit_length() - 1, X.bit_length() - 1
                if h in self.heart and self.leaves[x].kind == "room":
                    marked = self.canon({**dict(tX), x: dict(tX).get(x, 0) | lit})
                    if is_a:
                        tA = marked
                    else:
                        tB = marked
        got = axis, A, tA, O & ~second, B, tB, O & ~first, QA, QB, chk, wcost, wchk
        self._splits[mk] = got
        return got

    @staticmethod
    def _win_extra(wcost, wchk, ka, kb):
        """The windows' charge for one way of laying a cut: waived for each
        room that runs past the end of the lone stair hall across by a cell
        for every window asked on that wall (two gable windows beside a
        stair need two cells of it outside, not one), and in part where it
        runs past by fewer."""
        c = wcost
        for l_in_a, il, ih, n in wchk:
            el, eh = (ka[il], kb[ih]) if l_in_a else (kb[il], ka[ih])
            past = max(0, eh[0] - el[0]) + max(0, el[1] - eh[1])
            c -= WINDOW_COST * min(1.0, past / n)
        return c

    def pad_sides(self, keep, O):
        """Sides a strip of roof may be left on: never one a member must keep,
        and only where the strip reaches the outline -- along it, or across
        its end -- so roof is never a hole in a storey."""
        if self.pad is None or self.earth:
            return ()               # a dug storey's earth is its leaves' (`_earth_rel`)
        out = []
        for b in (1, 2, 4, 8):
            if keep & b:
                continue
            perp = _EW if b & _NS else _NS
            if O & b or O & perp:
                out.append(b)
        return out

    def _ledge(self, b, O, p, length):
        """A STRIP OF ROOF ALONG A WHOLE OUTER WALL OF A FULL STOREY
        (`LEDGE_COST`): a pad on side `b` of a part reaching the outline on
        that side and at both its ends, at most LEDGE_DEPTH deep."""
        if not self.ledge or not O & b or p > LEDGE_DEPTH:
            return 0.0
        perp = _EW if b & _NS else _NS
        return self.ledge * p * length if O & perp == perp else 0.0

    def _notch_sides(self, keep, O, door=0):
        """[(side bit, reflex corners, opening)]: the sides of a ground
        room's slot a notch may be left on (`NOTCH_COST`) -- never one the
        room must keep, save an outline side it keeps only for a door
        outdoors (`door`): the door opens onto the notch, a porch before it.
        'corner': the strip lies along the outline and reaches it at one end
        too (an L, one reflex corner); 'side': along the outline between two
        neighbours (a recess, two); 'end': from the outline into the house,
        its end on the outline (a porch, two). A strip along a whole side of
        the outline is a smaller outline, and one with neither end on the
        outline a hole or a cleft through the house: neither is a notch."""
        out = []
        for b in (1, 2, 4, 8):
            if keep & b and not (door & b and O & b):
                continue
            perp = _EW if b & _NS else _NS
            ends = bin(O & perp).count("1")
            if O & b:
                if ends < 2:
                    out.append((b, 1, "corner") if ends == 1 else (b, 2, "side"))
            elif ends == 1:
                out.append((b, 2, "end"))
        return out

    @staticmethod
    def _notch_floor(lf):
        """The least floor a ground room may keep and leave a notch: its
        target, less the slack whole paces leave (`STATED_SLACK`,
        `KEEP_SLACK`) -- a notch never makes a room smaller than it should
        be."""
        if lf.target <= 0:
            return 0.0
        return lf.target - (STATED_SLACK if lf.size_kind == "stated" else KEEP_SLACK)

    def _notched(self, key, core, i, keep, O, Q):
        """A GROUND ROOM'S SHAPES, AND EACH WITH A NOTCH (`NOTCH_COST`): one
        strip of open ground on one side of its slot (`_notch_sides`), at
        least NOTCH_MIN_SIDE paces across both ways, a strip open on one
        side running at most NOTCH_ASPECT times its opening into the house,
        the room keeping at least its target (`_notch_floor`). The room
        still faces outdoors across the strip -- its windows and doors on
        that wall look out over the notch -- so it loses nothing there. A
        strip run from the outline beside a dark heart room laid alone
        across the cut (`LIT_EW`, `LIT_NS`, `_split`) gives that room its
        wall to the outside: it takes back HEART_DARK_COST."""
        out = _Table()
        for k, c in core.cost.items():
            out.put(k, c, ("core",))
        least = self._notch_floor(self.leaves[i])
        lit = keep & (LIT_EW | LIT_NS)
        M = self.M
        for b, corners, opening in self._notch_sides(keep, O, self.doors.get(i, 0)):
            ew = bool(b & _EW)
            refund = HEART_DARK_COST if opening == "end" and lit & (LIT_EW if ew else LIT_NS) else 0.0
            for (w, h, k), c in core.cost.items():
                if w * h < least:
                    continue
                L = h if ew else w              # the strip's length, along the room's side
                if L < NOTCH_MIN_SIDE:
                    continue
                for p in range(NOTCH_MIN_SIDE, PAD_MAX + 1):
                    if (w + p if ew else h + p) > M:
                        break
                    if opening == "side" and p > NOTCH_ASPECT * L:
                        break                   # a cleft, not a recess
                    if opening == "end" and L > NOTCH_ASPECT * p:
                        continue                # a slot, not a porch
                    if p * L > NOTCH_SHARE_MAX * w * h:
                        break                   # more open ground than room
                    extra = NOTCH_COST * p * L + self.step_cost * corners - refund
                    if ew:
                        k2 = k if b == 2 or not Q else tuple(
                            (e[0] + p, e[1] + p) if q[1] == 0 else e for q, e in zip(Q, k))
                        out.put((w + p, h, k2), c + extra, ("pad", b, p, k))
                    else:
                        k2 = k if b == 4 or not Q else tuple(
                            (e[0] + p, e[1] + p) if q[1] == 1 else e for q, e in zip(Q, k))
                        out.put((w, h + p, k2), c + extra, ("pad", b, p, k))
        out.seal()
        self._tick(len(out.cost))
        self._tables[key] = out
        self._tables[("core",) + key] = core
        return out

    def _lost_sides(self, i, sides):
        """What leaf i's asks cost on the outline sides `sides` it no longer
        reaches: each window, and each block asked beyond (a cavern), on
        them -- what a cut taking those sides would have charged (`_wins`)."""
        c = 0.0
        for b in (1, 2, 4, 8):
            if sides & b:
                if self.wish.get(i, 0) & b:
                    c += WINDOW_COST
                if self.cave.get(i, 0) & b:
                    c += CAVE_SIDE_COST
        return c

    # -- the relative DP -----------------------------------------------------

    def leaf_table(self, i):
        """{(w, h): cost} of every shape a leaf may take, within LEAF_MARGIN
        of its cheapest: a room three times its size is never the answer,
        and keeping it costs every table above it."""
        lk = (i, self.leaves[i].flights) if self.leaves[i].kind == "hall" else i
        got = self._leaf_tables.get(lk)
        if got is None:
            got = {}
            lf = self.leaves[i]
            M = self.M
            for w in range(1, M + 1):
                for h in range(1, M + 1):
                    c = lf.cost(w, h)
                    if c < INF:
                        got[(w, h)] = c
            if got:
                cap = min(got.values()) + self.leaf_margin
                got = {k: c for k, c in got.items() if c <= cap}
            self._leaf_tables[lk] = got
        return got

    def table(self, S, T, O):
        return self.etable(S, T, O, ())

    def _combine(self, core, ci, EA, EB, axis, Q, QA, QB, chk, wcost, wchk):
        """Every way to lay part A beside part B across one cut, into `core`:
        a west|east cut sums widths at one height, a north|south cut heights
        at one width. A coupled cut's joins are checked on the extents along
        it. Where no ancestor reads extents (Q empty) each entry keeps only
        its cheapest, so both parts' entries are read cheapest first and the
        reading stops once it cannot win."""
        M = self.M
        pa = {q: n for n, q in enumerate(QA)}
        pb = {q: n for n, q in enumerate(QB)}
        least = wcost - WINDOW_COST * len(wchk)     # the windows' charge at its least
        win = self._win_extra
        shift_ax = 0 if axis == "v" else 1        # B's extents across the cut move by A's size
        build = [(0, pa[q], False) if q in pa else (1, pb[q], q[1] == shift_ax) for q in Q]
        ga, gb = EA.grouped(axis), EB.grouped(axis)
        bounds = {}
        key_cap = self.key_cap

        for shared, alist in ga.items():
            blist = gb.get(shared)
            if not blist:
                continue
            for own_a, ents_a in alist:
                for own_b, ents_b in blist:
                    tot = own_a + own_b
                    if tot > M:
                        break
                    w, h = (tot, shared) if axis == "v" else (shared, tot)
                    if not Q:
                        best = core.cost.get((w, h, ()), INF)
                        min_b = ents_b[0][0]
                        for ca, ka in ents_a:
                            if ca + min_b + least >= best:
                                break
                            for cb, kb in ents_b:
                                c = ca + cb
                                if c + least >= best:
                                    break
                                hx = _chk_cost(chk, ka, kb) if chk else 0.0
                                if hx == INF:
                                    continue
                                c += hx + (win(wcost, wchk, ka, kb) if wchk else wcost)
                                if c < best:
                                    best = c
                                    core.put((w, h, ()), c, ("cut", ci, own_a, ka, kb))
                                if not wchk and not hx:
                                    break
                        continue
                    # each shape keeps its KEY_CAP cheapest extents: a pair
                    # dearer than the KEY_CAP-th found is not read
                    kept = bounds.setdefault((w, h), [])
                    bound = kept[-1] if len(kept) >= key_cap else INF
                    min_b = ents_b[0][0]
                    for ca, ka in ents_a:
                        if ca + min_b + least >= bound:
                            break
                        for cb, kb in ents_b:
                            c = ca + cb
                            if c + least >= bound:
                                break
                            hx = _chk_cost(chk, ka, kb) if chk else 0.0
                            if hx == INF:
                                continue
                            c += hx + (win(wcost, wchk, ka, kb) if wchk else wcost)
                            out = tuple(ka[n] if src == 0 else
                                        ((kb[n][0] + own_a, kb[n][1] + own_a) if shift else kb[n])
                                        for src, n, shift in build)
                            core.put((w, h, out), c, ("cut", ci, own_a, ka, kb))
                            bisect.insort(kept, c)
                            del kept[key_cap:]
                            bound = kept[-1] if len(kept) >= key_cap else INF

    def ltable(self, S, T, O):
        """A LOWER BOUND on `etable(S, T, O, ())`, for the pinned storeys'
        branch and bound (`GE_core`, `rel_core_at`) and the region search:
        one table a set of leaves, whatever its touch demands and outline
        sides -- every cut the side order allows (uncapped, so no cut a
        touch demand keeps is missing), every coupled cut read as if its
        shared walls held, no window lost, roof allowed on every side. Each
        relaxation only lowers a cost, so the bound never passes the
        exact value."""
        key = ("bound", S, self._sig(S))
        got = self._tables.get(key)
        if got is not None:
            return got
        core = _Table()
        mem = self.members(S)
        if len(mem) == 1:
            for (w, h), c in self.leaf_table(mem[0]).items():
                core.put((w, h, ()), c, None)
        else:
            seen = set()
            # uncapped, so the bound stays below every capped search -- but
            # on a large storey, searched narrowly anyway, the capped list
            # (the uncapped one is the cost of a manor's every slicing tree)
            for axis, A, _tA, B, _tB, _loose in self.cuts(S, (), capped=self.couple_all):
                if (axis, A) in seen:
                    continue
                seen.add((axis, A))
                EA, EB = self.ltable(A, (), _ALL), self.ltable(B, (), _ALL)
                if EA.cost and EB.cost:
                    self._combine(core, 0, EA, EB, axis, (), (), (), (), 0.0, ())
        core.seal()
        self._tick(len(core.cost) + 1)
        if self.earth:
            if len(mem) > 1 or not core.cost:
                self._tables[key] = core
                return core
            # A LEAF OF A DUG STOREY TAKES ANY SHAPE ITS SLOT HOLDS, the rest
            # of the slot earth (`_earth_rel`): the least of every shape of it
            # inside W x H with the rest earth -- a prefix minimum of (cost -
            # earth under the leaf)
            M, pad = self.M, self.pad
            low = [[INF] * (M + 1) for _ in range(M + 1)]
            for (w, h, _k), c in core.cost.items():
                v = c - pad * w * h
                if v < low[w][h]:
                    low[w][h] = v
            for w in range(1, M + 1):
                row, prev = low[w], low[w - 1]
                for h in range(1, M + 1):
                    v = min(row[h], prev[h], row[h - 1])
                    row[h] = v
                    if v < INF:
                        core.put((w, h, ()), v + pad * w * h, None)
            core._at = None
            core._grouped = {}
        elif self.pad is not None and core.cost:
            M, pad = self.M, self.pad
            for (w, h, k), c in list(core.cost.items()):
                for p in range(1, PAD_MAX + 1):
                    if w + p <= M:
                        core.put((w + p, h, k), c + pad * p * h, None)
                    if h + p <= M:
                        core.put((w, h + p, k), c + pad * p * w, None)
            core._at = None
            core._grouped = {}
        self._tables[key] = core
        return core

    def etable(self, S, T, O, Q):
        """The least cost of laying the leaves of S, with touch demands T and
        outline sides O, in every w x h -- the minimum over every cut the
        relations allow, exact for the trees they allow -- keyed too by the
        extents of the leaves in Q ((leaf, axis): axis 0 = x, 1 = y) an
        ancestor's coupled cut reads."""
        key = (S, T, O, Q, self._sig(S))
        got = self._tables.get(key)
        if got is not None:
            return got
        core = _Table()
        mem = self.members(S)
        if len(mem) == 1:
            i = mem[0]
            extra = self.leaf_extra(i, O)
            for (w, h), c in self.leaf_table(i).items():
                k = tuple((0, w) if ax == 0 else (0, h) for _l, ax in Q)
                core.put((w, h, k), c + extra, ("leaf",))
        else:
            M = self.M
            cuts = self.cuts(S, T)
            narrow = None
            for ci in range(len(cuts)):
                # a storey gone narrow mid-solve reads the rest narrowly
                # (`_read`), this set's loop too
                if self.narrowed:
                    narrow = set(self._read(cuts)) if narrow is None else narrow
                    if ci not in narrow:
                        continue
                axis, A, tA, OA, B, tB, OB, QA, QB, chk, wcost, wchk = self._split(cuts[ci], Q, O)
                EA = self.etable(A, tA, OA, QA)
                EB = self.etable(B, tB, OB, QB)
                if not EA.cost or not EB.cost:
                    continue
                self._combine(core, ci, EA, EB, axis, Q, QA, QB, chk, wcost, wchk)
        core.seal()
        self._tick(len(core.cost) + 1)
        keep = 0
        for _i, m in T:
            keep |= m
        if self.notch and len(mem) == 1 and mem[0] in self.notch_at and core.cost:
            return self._notched(key, core, mem[0], keep, O, Q)
        sides = self.pad_sides(keep, O)
        if not sides or not core.cost:
            self._tables[key] = core
            self._tables[("core",) + key] = core
            return core
        out = _Table()
        for k, c in core.cost.items():
            out.put(k, c, ("core",))
        pad = self.pad
        M = self.M
        for (w, h, k), c in core.cost.items():
            for b in sides:
                for p in range(1, PAD_MAX + 1):
                    if b & _EW:
                        if w + p > M:
                            break
                        # a strip on the west moves the core's x-extents east
                        k2 = k if b == 2 or not Q else tuple(
                            (e[0] + p, e[1] + p) if q[1] == 0 else e for q, e in zip(Q, k))
                        out.put((w + p, h, k2), c + pad * p * h + self._ledge(b, O, p, h), ("pad", b, p, k))
                    else:
                        if h + p > M:
                            break
                        k2 = k if b == 4 or not Q else tuple(
                            (e[0] + p, e[1] + p) if q[1] == 1 else e for q, e in zip(Q, k))
                        out.put((w, h + p, k2), c + pad * p * w + self._ledge(b, O, p, w), ("pad", b, p, k))
        out.seal()
        self._tick(len(out.cost))
        self._tables[key] = out
        self._tables[("core",) + key] = core
        return out

    def rel_at(self, S, T, O, Q, w, h):
        """{key: (cost, how)}: `etable` read top-down for one shape -- the
        ways of laying S in w x h with the extents of Q -- for a pinned
        storey's coupled cuts, which ask few shapes of many keyed tables."""
        mk = ("at", S, T, O, Q, w, h, self._sig(S))
        got = self._tables.get(mk)
        if got is not None:
            return got
        self._tables[mk] = {}
        res = dict(self.rel_core_at(S, T, O, Q, w, h))
        keep = 0
        for _i, m in T:
            keep |= m
        for b in self.pad_sides(keep, O):
            for p in range(1, PAD_MAX + 1):
                if b & _EW and p >= w or b & _NS and p >= h:
                    break
                sub = self.rel_core_at(S, T, O, Q, w - p if b & _EW else w, h - p if b & _NS else h)
                add = self.pad * p * (h if b & _EW else w) + self._ledge(b, O, p, h if b & _EW else w)
                for k, (c, _how) in sub.items():
                    k2 = k
                    if b in (8, 1):
                        ax0 = 0 if b == 8 else 1
                        k2 = tuple((e[0] + p, e[1] + p) if q[1] == ax0 else e for q, e in zip(Q, k))
                    if c + add < res.get(k2, (INF,))[0]:
                        res[k2] = (c + add, ("pad", b, p, k))
        if len(res) > self.key_cap:
            res = dict(sorted(res.items(), key=lambda t: (t[1][0], t[0]))[:self.key_cap])
        self._tables[mk] = res
        return res

    def rel_core_at(self, S, T, O, Q, w, h):
        mk = ("core_at", S, T, O, Q, w, h, self._sig(S))
        got = self._tables.get(mk)
        if got is not None:
            return got
        res = {}
        if w < 1 or h < 1:
            self._tables[mk] = res
            return res
        mem = self.members(S)
        if len(mem) == 1:
            i = mem[0]
            if self.earth:
                res = self._earth_rel(i, T, O, Q, w, h)
                self._tables[mk] = res
                self._tick(len(res) + 1)
                return res
            c = self.leaf_table(i).get((w, h))
            if c is not None:
                k = tuple((0, w) if ax == 0 else (0, h) for _l, ax in Q)
                res[k] = (c + self.leaf_extra(i, O), ("leaf",))
            self._tables[mk] = res
            return res
        cand = []
        cuts = self.cuts(S, T)
        for ci in self._read(cuts):
            axis, A, tA, B, tB, loose = cuts[ci]
            first, second = (8, 2) if axis == "v" else (1, 4)
            RA = self.ltable(A, tA, O & ~second)
            RB = self.ltable(B, tB, O & ~first)
            span = w if axis == "v" else h
            for k in range(1, span):
                wa, ha = (k, h) if axis == "v" else (w, k)
                wb, hb = (w - k, h) if axis == "v" else (w, h - k)
                la = RA.get(wa, ha)
                if la < INF:
                    lb = RB.get(wb, hb)
                    if lb < INF:
                        cand.append((la + lb, ci, k))
        cand.sort()
        best = INF
        narrow = None
        for bound, ci, k in cand:
            if not Q and bound >= best:
                break
            if self.narrowed:
                narrow = set(self._read(cuts)) if narrow is None else narrow
                if ci not in narrow:
                    continue
            axis, A, tA, OA, B, tB, OB, QA, QB, chk, wcost, wchk = self._split(cuts[ci], Q, O)
            least = wcost - WINDOW_COST * len(wchk)
            if not Q and bound + least >= best:
                continue
            wa, ha = (k, h) if axis == "v" else (w, k)
            wb, hb = (w - k, h) if axis == "v" else (w, h - k)
            EA = self.rel_at(A, tA, OA, QA, wa, ha)
            if not EA:
                continue
            EB = self.rel_at(B, tB, OB, QB, wb, hb)
            if not EB:
                continue
            pa = {q: n for n, q in enumerate(QA)}
            pb = {q: n for n, q in enumerate(QB)}
            shift_ax = 0 if axis == "v" else 1
            for ka, (ca, _ha) in sorted(EA.items(), key=lambda t: t[1][0]):
                for kb, (cb, _hb) in sorted(EB.items(), key=lambda t: t[1][0]):
                    c = ca + cb
                    if not Q and c + least >= best:
                        break
                    hx = _chk_cost(chk, ka, kb) if chk else 0.0
                    if hx == INF:
                        continue
                    c += hx + (self._win_extra(wcost, wchk, ka, kb) if wchk else wcost)
                    out = tuple(ka[pa[q]] if q in pa else
                                ((kb[pb[q]][0] + k, kb[pb[q]][1] + k) if q[1] == shift_ax else kb[pb[q]])
                                for q in Q)
                    if c < res.get(out, (INF,))[0]:
                        res[out] = (c, ("cut", ci, k, ka, kb))
                        if not Q:
                            best = c
                    if not Q and not wchk and not hx:
                        break
        self._tables[mk] = res
        self._tick(len(res) + 1)
        return res

    def place_at(self, S, T, O, Q, w, h, key, x, y, out, pads):
        """Lay S in w x h at (x, y) as `rel_at` chose for extents `key`."""
        how = self.rel_at(S, T, O, Q, w, h)[key][1]
        if how[0] == "pad":
            _p, b, p, key = how
            if b == 8:
                pads.append(Rect(x, y, p, h))
                x, w = x + p, w - p
            elif b == 2:
                pads.append(Rect(x + w - p, y, p, h))
                w -= p
            elif b == 1:
                pads.append(Rect(x, y, w, p))
                y, h = y + p, h - p
            else:
                pads.append(Rect(x, y + h - p, w, p))
                h -= p
            how = self.rel_core_at(S, T, O, Q, w, h)[key][1]
        else:
            how = self.rel_core_at(S, T, O, Q, w, h)[key][1]
        if how[0] == "leaf":
            out[self.members(S)[0]] = Rect(x, y, w, h)
            return
        if how[0] == "earth":
            _e, x0, y0, lw, lh = how
            room = Rect(x + x0, y + y0, lw, lh)
            out[self.members(S)[0]] = room
            pads.extend(_earth_rects(Rect(x, y, w, h), room))
            return
        _t, ci, k, ka, kb = how
        axis, A, tA, OA, B, tB, OB, QA, QB, _chk, _w, _wc = self._split(self.cuts(S, T)[ci], Q, O)
        for part, tP, OP, QP, kp, (px, py, pw, ph) in (
                (A, tA, OA, QA, ka, (x, y, k, h) if axis == "v" else (x, y, w, k)),
                (B, tB, OB, QB, kb, (x + k, y, w - k, h) if axis == "v" else (x, y + k, w, h - k))):
            self.place_at(part, tP, OP, QP, pw, ph, kp, px, py, out, pads)

    def place(self, S, T, O, x, y, w, h, out, pads, Q=(), k=()):
        """Follow the table's choices down to rectangles: `out` {leaf: Rect},
        `pads` [Rect] of roof."""
        key = (S, T, O, Q, self._sig(S))
        tab = self.etable(S, T, O, Q)
        how = tab.back[(w, h, k)]
        if how[0] == "core":
            tab = self._tables[("core",) + key]
            how = tab.back[(w, h, k)]
        elif how[0] == "pad":
            _p, b, p, k = how
            if b == 8:
                pads.append(Rect(x, y, p, h))
                x, w = x + p, w - p
            elif b == 2:
                pads.append(Rect(x + w - p, y, p, h))
                w -= p
            elif b == 1:
                pads.append(Rect(x, y, w, p))
                y, h = y + p, h - p
            else:
                pads.append(Rect(x, y + h - p, w, p))
                h -= p
            tab = self._tables[("core",) + key]
            how = tab.back[(w, h, k)]
        if how[0] == "leaf":
            out[self.members(S)[0]] = Rect(x, y, w, h)
            return
        _c, ci, cut, ka, kb = how
        axis, A, tA, OA, B, tB, OB, QA, QB, _chk, _w, _wc = self._split(self.cuts(S, T)[ci], Q, O)
        if axis == "v":
            self.place(A, tA, OA, x, y, cut, h, out, pads, QA, ka)
            self.place(B, tB, OB, x + cut, y, w - cut, h, out, pads, QB, kb)
        else:
            self.place(A, tA, OA, x, y, w, cut, out, pads, QA, ka)
            self.place(B, tB, OB, x, y + cut, w, h - cut, out, pads, QB, kb)

    # -- a dug storey's leaf in its slot ----------------------------------------

    def _earth_rel(self, i, T, O, Q, W, H):
        """A ROOM OF A DUG STOREY IN ITS SLOT (`EARTH_COST`): every shape of
        it the slot W x H holds, the rest of the slot earth -- the room takes
        what it needs and no more. It stands flush with the sides of the slot
        it must keep (`T`), and where its place along an axis matters to an
        ancestor (its extents, `Q`) at every place along it, a shade dearer
        off the slot's sides (EARTH_SHIFT) so the flush places are read first;
        else flush with one side or the other. What of the outline it no
        longer reaches costs its asks there (`_lost_sides`). {key: (cost,
        ("earth", x0, y0, w, h))}, relative to the slot."""
        keep = 0
        for j, m in T:
            if j == i:
                keep |= m
        qx = any(ax == 0 for _l, ax in Q)
        qy = any(ax == 1 for _l, ax in Q)
        e = self.pad
        res = {}
        for (w, h), c in self.leaf_table(i).items():
            if w > W or h > H:
                continue
            base = c + e * (W * H - w * h)
            xs = range(W - w + 1) if qx else sorted({0, W - w})
            ys = range(H - h + 1) if qy else sorted({0, H - h})
            for x0 in xs:
                tx = (8 if x0 == 0 else 0) | (2 if x0 + w == W else 0)
                for y0 in ys:
                    touch = tx | (1 if y0 == 0 else 0) | (4 if y0 + h == H else 0)
                    if keep & ~touch:
                        continue
                    cost = base + self._lost_sides(i, O & ~touch) + self.leaf_extra(i, O & touch) + \
                        EARTH_SHIFT * (min(x0, W - w - x0) + min(y0, H - h - y0))
                    k = tuple((x0, x0 + w) if ax == 0 else (y0, y0 + h) for _l, ax in Q)
                    if cost < res.get(k, (INF,))[0]:
                        res[k] = (cost, ("earth", x0, y0, w, h))
        return res

    def _hall_rects(self, i):
        """Every hall a pinned flight of a dug storey may take: the flight,
        at least HALL_MIN_ACROSS across it, landing at most LANDING_MAX along
        its run (`Leaf.abs_cost`) -- [(Rect, cost)], computed once."""
        got = self._halls.get(i)
        if got is None:
            lf = self.leaves[i]
            f = lf.pin
            got = []
            for hw in range(f.w, f.w + LANDING_MAX + HALL_MIN_ACROSS + 1):
                for hd in range(f.d, f.d + LANDING_MAX + HALL_MIN_ACROSS + 1):
                    for hx in range(f.x + f.w - hw, f.x + 1):
                        for hy in range(f.y + f.d - hd, f.y + 1):
                            c = lf.abs_cost(hx, hy, hw, hd)
                            if c < INF:
                                got.append((Rect(hx, hy, hw, hd), c))
            self._halls[i] = got
        return got

    def _earth_abs(self, i, T, O, Q, x, y, W, H):
        """A PINNED STAIR HALL OF A DUG STOREY IN ITS SLOT (x, y, W, H): its
        flight and a landing within LANDING_MAX (`_hall_rects`), the rest of
        the slot earth -- never a landing grown to fill a storey. As
        `_earth_rel`, absolute: {key: (cost, ("earth", x, y, w, d))}."""
        keep = 0
        for j, m in T:
            if j == i:
                keep |= m
        e = self.pad
        res = {}
        for r, c in self._hall_rects(i):
            if r.x < x or r.y < y or r.x + r.w > x + W or r.y + r.d > y + H:
                continue
            touch = (8 if r.x == x else 0) | (2 if r.x + r.w == x + W else 0) | \
                (1 if r.y == y else 0) | (4 if r.y + r.d == y + H else 0)
            if keep & ~touch:
                continue
            cost = c + e * (W * H - r.w * r.d) + self._lost_sides(i, O & ~touch) + self.leaf_extra(i, O & touch)
            k = tuple((r.x, r.x + r.w) if ax == 0 else (r.y, r.y + r.d) for _l, ax in Q)
            if cost < res.get(k, (INF,))[0]:
                res[k] = (cost, ("earth", r.x, r.y, r.w, r.d))
        return res

    # -- the absolute DP (a storey with flights pinned) ------------------------

    def holds_pins(self, S, x, y, w, h):
        m = S & self.pinned
        i = 0
        while m:
            if m & 1:
                f = self.leaves[i].pin
                if not (x <= f.x and y <= f.y and x + w >= f.x + f.w and y + h >= f.y + f.d):
                    return False
            m >>= 1
            i += 1
        return True

    def _check(self, loose, QA, QB, ax):
        """The coupled joins of a cut as index pairs into its parts' keys
        (their extents along the cut, axis `ax`) -- with, for a room reaching
        a flight across the landing beside it (ACROSS_END), the flight's own
        extent there."""
        out = []
        for a, b, need, end in loose:
            fe = None
            if end == ACROSS_END:
                f = self.leaves[a if self.leaves[a].kind == "hall" else b].pin
                fe = (f.x, f.x + f.w) if ax == 0 else (f.y, f.y + f.d)
            # a negative need: one pace held, -need wanted (`_min_shared`)
            out.append((QA.index((a, ax)), QB.index((b, ax)), 1 if need < 0 else need, end,
                        self.leaves[a].kind == "hall", fe, -need if need < 0 else 0))
        return out

    def GE(self, S, T, O, Q, x, y, w, h, root=False):
        """The pinned DP: {extents key: cost} of laying the leaves of S in the
        absolute rectangle (x, y, w, h), its pinned halls holding their
        flights where they stand. `key` gives, for each (leaf, axis) of Q, the
        leaf's absolute extent on that axis, so a coupled cut above checks
        its shared walls exactly. A set holding no pin reads the relative
        table (`etable`), shifted to (x, y)."""
        mk = (S, T, O, Q, x, y, w, h, root)
        got = self._g.get(mk)
        if got is not None:
            return got[0]
        self._g[mk] = ({}, {})
        if w < 1 or h < 1 or not self.holds_pins(S, x, y, w, h):
            return {}
        res, how = self.GE_core(S, T, O, Q, x, y, w, h)
        res, how = dict(res), {k: ("core",) for k in res}
        if not root and S & self.absmask:
            keep = 0
            for _i, m in T:
                keep |= m
            for b in self.pad_sides(keep, O):
                for p in range(1, PAD_MAX + 1):
                    if b & _EW and p >= w or b & _NS and p >= h:
                        break
                    if b == 8:
                        sub = self.GE_core(S, T, O, Q, x + p, y, w - p, h)[0]
                    elif b == 2:
                        sub = self.GE_core(S, T, O, Q, x, y, w - p, h)[0]
                    elif b == 1:
                        sub = self.GE_core(S, T, O, Q, x, y + p, w, h - p)[0]
                    else:
                        sub = self.GE_core(S, T, O, Q, x, y, w, h - p)[0]
                    add = self.pad * p * (h if b & _EW else w) + self._ledge(b, O, p, h if b & _EW else w)
                    for k, c in sub.items():
                        if c + add < res.get(k, INF):
                            res[k] = c + add
                            how[k] = ("pad", b, p)
        if len(res) > self.key_cap:
            keep_k = sorted(res, key=lambda k: (res[k], k))[:self.key_cap]
            res = {k: res[k] for k in keep_k}
            how = {k: how[k] for k in keep_k}
        self._g[mk] = (res, how)
        return res

    def GE_core(self, S, T, O, Q, x, y, w, h):
        mk = (S, T, O, Q, x, y, w, h)
        got = self._gcore.get(mk)
        if got is not None:
            return got
        if w < 1 or h < 1 or not self.holds_pins(S, x, y, w, h):
            self._gcore[mk] = ({}, {})
            return self._gcore[mk]
        res, how = {}, {}
        if not S & self.absmask:
            for k, (c, _how) in self.rel_at(S, T, O, Q, w, h).items():
                ak = tuple((e[0] + x, e[1] + x) if q[1] == 0 else (e[0] + y, e[1] + y) for q, e in zip(Q, k))
                if c < res.get(ak, INF):
                    res[ak] = c
                    how[ak] = ("rel", k)
            self._gcore[mk] = (res, how)
            return self._gcore[mk]
        mem = self.members(S)
        if len(mem) == 1:
            i = mem[0]
            if self.earth:
                for k, (c, hw) in self._earth_abs(i, T, O, Q, x, y, w, h).items():
                    res[k], how[k] = c, hw
                self._gcore[mk] = (res, how)
                return self._gcore[mk]
            if self.leaves[i].pin is not None:
                c = self.leaves[i].abs_cost(x, y, w, h) + self.leaf_extra(i, O)
            else:
                # an upper room off the rooms its stair climbs from (OVER_COST)
                c = self.leaf_table(i).get((w, h), INF) + self.leaf_extra(i, O)
                if c < INF:
                    on = sum(max(0, min(x + w, r.x + r.w) - max(x, r.x)) * max(0, min(y + h, r.y + r.d) - max(y, r.y))
                             for r in self.over[i])
                    c += OVER_COST * (w * h - on)
            if c < INF:
                k = tuple((x, x + w) if ax == 0 else (y, y + h) for _l, ax in Q)
                res[k], how[k] = c, ("leaf",)
            self._gcore[mk] = (res, how)
            return self._gcore[mk]
        # BRANCH AND BOUND: the relative tables bound the pinned costs from
        # below (a pin only takes shapes away), so every cut and position is
        # ranked by its free cost and read in that order; where no ancestor
        # reads extents (Q empty) the reading stops once the free cost alone
        # passes the best pinned one found
        cand = []
        cuts = self.cuts(S, T)
        for ci in self._read(cuts):
            axis, A, tA, B, tB, loose = cuts[ci]
            first, second = (8, 2) if axis == "v" else (1, 4)
            RA = self.ltable(A, tA, O & ~second)
            RB = self.ltable(B, tB, O & ~first)
            if axis == "v":
                for k in range(1, w):
                    la = RA.get(k, h)
                    if la < INF:
                        lb = RB.get(w - k, h)
                        if lb < INF:
                            cand.append((la + lb, ci, k))
            else:
                for k in range(1, h):
                    la = RA.get(w, k)
                    if la < INF:
                        lb = RB.get(w, h - k)
                        if lb < INF:
                            cand.append((la + lb, ci, k))
        cand.sort()
        best = INF
        narrow = None
        for bound, ci, k in cand:
            if not Q and bound >= best:
                break
            if self.narrowed:
                narrow = set(self._read(cuts)) if narrow is None else narrow
                if ci not in narrow:
                    continue
            axis, A, tA, OA, B, tB, OB, QA, QB, chk, wcost, wchk = self._split(cuts[ci], Q, O)
            least = wcost - WINDOW_COST * len(wchk)
            if not Q and bound + least >= best:
                continue
            if axis == "v":
                ra, rb = (x, y, k, h), (x + k, y, w - k, h)
            else:
                ra, rb = (x, y, w, k), (x, y + k, w, h - k)
            EA = self.GE(A, tA, OA, QA, *ra)
            if not EA:
                continue
            EB = self.GE(B, tB, OB, QB, *rb)
            if not EB:
                continue
            pa = {q: n for n, q in enumerate(QA)}
            pb = {q: n for n, q in enumerate(QB)}
            for ka, ca in sorted(EA.items(), key=lambda t: t[1]):
                if not Q and ca + min(EB.values()) + least >= best:
                    break
                for kb, cb in sorted(EB.items(), key=lambda t: t[1]):
                    c = ca + cb
                    if not Q and c + least >= best:
                        break
                    hx = _chk_cost(chk, ka, kb) if chk else 0.0
                    if hx == INF:
                        continue
                    c += hx + (self._win_extra(wcost, wchk, ka, kb) if wchk else wcost)
                    out = tuple(ka[pa[q]] if q in pa else kb[pb[q]] for q in Q)
                    if c < res.get(out, INF):
                        res[out] = c
                        how[out] = ("cut", ci, k, ka, kb)
                        if not Q:
                            best = c
                    if not Q and not wchk and not hx:
                        break
        self._gcore[mk] = (res, how)
        self._tick(len(res) + 1)
        return self._gcore[mk]

    def G(self, S, T, O, x, y, w, h, root=False):
        """The least pinned cost of S in the absolute rectangle (`GE`)."""
        return self.GE(S, T, O, (), x, y, w, h, root).get((), INF)

    def place_abs(self, S, T, O, x, y, w, h, out, pads, root=False, Q=(), key=()):
        mk = (S, T, O, Q, x, y, w, h, root)
        _res, how_d = self._g[mk]
        how = how_d[key]
        if how[0] == "pad":
            _p, b, p = how
            if b == 8:
                pads.append(Rect(x, y, p, h))
                x, w = x + p, w - p
            elif b == 2:
                pads.append(Rect(x + w - p, y, p, h))
                w -= p
            elif b == 1:
                pads.append(Rect(x, y, w, p))
                y, h = y + p, h - p
            else:
                pads.append(Rect(x, y + h - p, w, p))
                h -= p
        _res, how_c = self._gcore[(S, T, O, Q, x, y, w, h)]
        how = how_c[key]
        if how[0] == "rel":
            self.place_at(S, T, O, Q, w, h, how[1], x, y, out, pads)
            return
        if how[0] == "leaf":
            out[self.members(S)[0]] = Rect(x, y, w, h)
            return
        if how[0] == "earth":
            _e, hx, hy, hw, hd = how
            hall = Rect(hx, hy, hw, hd)
            out[self.members(S)[0]] = hall
            pads.extend(_earth_rects(Rect(x, y, w, h), hall))
            return
        _t, ci, k, ka, kb = how
        axis, A, tA, OA, B, tB, OB, QA, QB, _chk, _w, _wc = self._split(self.cuts(S, T)[ci], Q, O)
        if axis == "v":
            self.place_abs(A, tA, OA, x, y, k, h, out, pads, False, QA, ka)
            self.place_abs(B, tB, OB, x + k, y, w - k, h, out, pads, False, QB, kb)
        else:
            self.place_abs(A, tA, OA, x, y, w, k, out, pads, False, QA, ka)
            self.place_abs(B, tB, OB, x, y + k, w, h - k, out, pads, False, QB, kb)


def _chk_cost(chk, ka, kb):
    """What a coupled cut's joins cost on these extents (`_Storey._check`):
    INF where one does not hold -- the two do not share the wall they need,
    or a stair's room does not reach the end of the flight it must --
    HEAD_SHARED_COST for each room meeting a corridor at its stair's end by
    fewer paces than it wants (`_Storey._min_shared`), else 0."""
    x = 0.0
    for ia, ib, need, end, a_hall, fe, want in chk:
        ea, eb = ka[ia], kb[ib]
        lo = ea[0] if ea[0] > eb[0] else eb[0]
        hi = ea[1] if ea[1] < eb[1] else eb[1]
        # a wall as long as the room's own side is all it can share
        if hi - lo < min(need, ea[1] - ea[0], eb[1] - eb[0]):
            return INF
        if want and hi - lo < min(want, ea[1] - ea[0], eb[1] - eb[0]):
            x += HEAD_SHARED_COST
        if end:
            hall, room = (ea, eb) if a_hall else (eb, ea)
            if end == ACROSS_END:
                if not _across_ok(hall, room, fe):
                    return INF
                continue
            lo_end = room[0] <= hall[0] < room[1]
            hi_end = room[0] <= hall[1] - 1 < room[1]
            if end == ALL_ENDS:
                if not (lo_end or hi_end):
                    return INF
            elif end in (8, 1):
                if not lo_end:
                    return INF
            elif not hi_end:
                return INF
    return x


def _across_ok(hall, room, flight):
    """Does a room whose wall meets a stair hall's end (extents along that
    wall: `hall`, `room`) share a cell of it with the landing beside the
    flight (`flight`, the flight's extent there) -- the cell its doorway
    opens onto, to reach the far end of the flight across the landing?"""
    f0, f1 = flight
    return min(room[1], f0) - max(room[0], hall[0]) > 0 or min(room[1], hall[1]) - max(room[0], f1) > 0


def _earth_rects(slot, inner):
    """The earth of a dug storey's slot round the leaf standing in it: the
    slot less `inner`, as at most four rectangles (`Layout.earth`)."""
    out = []
    if inner.x > slot.x:
        out.append(Rect(slot.x, slot.y, inner.x - slot.x, slot.d))
    if inner.x + inner.w < slot.x + slot.w:
        out.append(Rect(inner.x + inner.w, slot.y, slot.x + slot.w - inner.x - inner.w, slot.d))
    if inner.y > slot.y:
        out.append(Rect(inner.x, slot.y, inner.w, inner.y - slot.y))
    if inner.y + inner.d < slot.y + slot.d:
        out.append(Rect(inner.x, inner.y + inner.d, inner.w, slot.y + slot.d - inner.y - inner.d))
    return out


# ---------------------------------------------------------------- regions

def _sub_rects(allowed, box, pins=(), min_area=1, max_area=None):
    """Every rectangle inside `box` all of whose cells are `allowed` and that
    holds every rectangle of `pins`, as (x, y, w, h), smallest area first.
    A 2-D prefix sum makes each test O(1)."""
    bx, by, bw, bh = box.x, box.y, box.w, box.d
    pre = [[0] * (bw + 1) for _ in range(bh + 1)]
    for j in range(bh):
        row = 0
        for i in range(bw):
            row += (bx + i, by + j) in allowed
            pre[j + 1][i + 1] = pre[j][i + 1] + row
    if pins:
        px0 = min(p.x for p in pins) - bx
        py0 = min(p.y for p in pins) - by
        px1 = max(p.x + p.w for p in pins) - bx
        py1 = max(p.y + p.d for p in pins) - by
    else:
        px0, py0, px1, py1 = bw, bh, 0, 0
    out = []
    # THE LOOPS ARE BOUNDED BY THE AREAS (the code review's finding 14: all
    # four ran in full whatever the bounds, 3 to 5 s a try on a large box):
    # a width whose least height already passes `max_area` ends the widths,
    # and each height runs only between the areas' own bounds -- the same
    # rectangles, found without reading the rest
    least_h = max(1, py1 - min(py0, bh - 1)) if pins else 1
    for x0 in range(0, min(px0, bw - 1) + 1):
        for x1 in range(max(x0 + 1, px1), bw + 1):
            w = x1 - x0
            if max_area is not None and w * least_h > max_area:
                break
            for y0 in range(0, min(py0, bh - 1) + 1):
                lo = max(y0 + 1, py1, y0 + int(math.ceil(min_area / w)))
                hi = bh if max_area is None else min(bh, y0 + int(max_area // w))
                for y1 in range(lo, hi + 1):
                    a = w * (y1 - y0)
                    if pre[y1][x1] - pre[y0][x1] - pre[y1][x0] + pre[y0][x0] != a:
                        continue
                    out.append((bx + x0, by + y0, w, y1 - y0))
    out.sort(key=lambda r: (r[2] * r[3], r[1], r[0], r[2]))
    return out


def _walls_meet(a, b):
    """Do rectangles `a` and `b` share a stretch of wall?"""
    if a.x + a.w == b.x or b.x + b.w == a.x:
        return min(a.y + a.d, b.y + b.d) > max(a.y, b.y)
    if a.y + a.d == b.y or b.y + b.d == a.y:
        return min(a.x + a.w, b.x + b.w) > max(a.x, b.x)
    return False


def _steps(rects):
    """(reflex corners, connected) of the footprint the rectangles cover --
    the ground's outline as a person walking round the house meets it: an L
    has one reflex corner, a porch or a recess two; a cleft that parts the
    house leaves it unconnected (GROUND_STEPS_MAX)."""
    cells = set()
    for r in rects:
        cells |= r.cells()
    if not cells:
        return 0, True
    x0, x1 = min(c[0] for c in cells), max(c[0] for c in cells) + 1
    y0, y1 = min(c[1] for c in cells), max(c[1] for c in cells) + 1
    corners = 0
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            q = [(x - 1, y - 1) in cells, (x, y - 1) in cells, (x - 1, y) in cells, (x, y) in cells]
            n = sum(q)
            if n == 3:
                corners += 1
            elif n == 2 and q[0] == q[3]:
                corners += 2                    # two rooms meeting at a corner only
    seen, stack = set(), [next(iter(cells))]
    while stack:
        c = stack.pop()
        if c in seen or c not in cells:
            continue
        seen.add(c)
        stack.extend((c[0] + dx, c[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    return (corners if len(seen) == len(cells) else corners + 2 * GROUND_STEPS_MAX + 2), len(seen) == len(cells)


def _set_back(allowed, x, y, w, h):
    """The cells of floor `allowed` (the storey below) in a strip at most
    LEDGE_DEPTH deep along a whole side of the outline (x, y, w, h), beyond
    which the floor ends: the ledge of roof a storey set back from the walls
    below leaves (`LEDGE_COST`)."""
    out = 0
    for dx, dy, n, at in ((0, -1, w, lambda k, i: (x + i, y - k)), (0, 1, w, lambda k, i: (x + i, y + h - 1 + k)),
                          (-1, 0, h, lambda k, i: (x - k, y + i)), (1, 0, h, lambda k, i: (x + w - 1 + k, y + i))):
        d = 0
        while d <= LEDGE_DEPTH and all(at(d + 1, i) in allowed for i in range(n)):
            d += 1
        if 1 <= d <= LEDGE_DEPTH:
            out += d * n
    return out


def _pad_ledge(outline, rects):
    """The roof cells of a storey in a strip at most LEDGE_DEPTH deep along a
    whole side of its outline -- a ledge left inside it (`LEDGE_COST`)."""
    floor = set()
    for r in rects:
        floor |= r.cells()
    x, y, w, h = outline.x, outline.y, outline.w, outline.d
    out = 0
    for n, at in ((w, lambda k, i: (x + i, y + k)), (w, lambda k, i: (x + i, y + h - 1 - k)),
                  (h, lambda k, i: (x + k, y + i)), (h, lambda k, i: (x + w - 1 - k, y + i))):
        d = 0
        while d <= LEDGE_DEPTH and all(at(d, i) not in floor for i in range(n)):
            d += 1
        if 1 <= d <= LEDGE_DEPTH:
            out += d * n
    return out


def _stands(laid):
    """Does a ground laid with notches stand as a person would build it: at
    most GROUND_STEPS_MAX reflex corners, its rooms one connected house, and
    reaching every side of the outline (notches on every side of a side
    would be a smaller outline)?"""
    corners, connected = _steps(laid.rects.values())
    if not connected or corners > GROUND_STEPS_MAX:
        return False
    o = laid.outline
    rs = list(laid.rects.values())
    return (min(r.x for r in rs) == o.x and min(r.y for r in rs) == o.y and
            max(r.x + r.w for r in rs) == o.x + o.w and max(r.y + r.d for r in rs) == o.y + o.d)


def _flight_ends(f):
    """The two ends of a straight flight (cells), keyed by the side bit they
    face: west/east for a flight running east-west, north/south else."""
    if f.w >= f.d:
        return {8: {(f.x, f.y + j) for j in range(f.d)}, 2: {(f.x + f.w - 1, f.y + j) for j in range(f.d)}}
    return {1: {(f.x + i, f.y) for i in range(f.w)}, 4: {(f.x + i, f.y + f.d - 1) for i in range(f.w)}}


#: A flight stands along a room's wall with at most this many paces of its
#: hall's own landing between (the sensible check's ALONG_GAP): a hall that
#: takes a landing across its run (LANDING_OVER_COST) lays it between the
#: flight and the room it serves, the floor the room's doorway opens onto
#: and from which either end is reached -- laid on the far side of the
#: flight it was sealed (the code review's e26: a 5-cell row behind the
#: flight, reached by no doorway).
ALONG_GAP = 1


def _along(flight, room, gap=0):
    """Does `room` stand along `flight` -- its wall beside the flight's long
    side, at most `gap` paces off it, for at least half the shorter of the
    run and the wall -- as the sensible check's 'along' reads it? 1 or 0."""
    run_ew = flight.w >= flight.d
    if run_ew:
        off = max(room.y - flight.y - flight.d, flight.y - room.y - room.d)
        if 0 <= off <= gap:
            over = min(room.x + room.w, flight.x + flight.w) - max(room.x, flight.x)
            return int(over >= max(1, min(flight.w, room.w) / 2))
    else:
        off = max(room.x - flight.x - flight.w, flight.x - room.x - room.w)
        if 0 <= off <= gap:
            over = min(room.y + room.d, flight.y + flight.d) - max(room.y, flight.y)
            return int(over >= max(1, min(flight.d, room.d) / 2))
    return 0


def _sealed(hall, flight, rooms, takes, enclosed):
    """THE LANDING NOBODY REACHES (the review's visual 3): the cells of
    `hall` off `flight` that a body on its storey reaches only across the
    flight, read as the review's audit reads them -- from the cells the
    served `rooms`' walls open onto the hall (an open stair's whole shared
    wall), and, for an enclosed stair, from the ends of the flight the storey
    takes (`takes`, side bits), whose doorway the lab opens beside that end."""
    from world.layout_solver import _shared_wall
    land = hall.cells() - flight.cells()
    if not land:
        return 0
    fc = flight.cells()
    seeds = set()
    if enclosed:
        ends = _flight_ends(flight)
        for b in takes:
            for c in ends.get(b, ()):
                for dx, dy in _STEP.values():
                    if (c[0] + dx, c[1] + dy) in land:
                        seeds.add((c[0] + dx, c[1] + dy))
    else:
        for r in rooms:
            _side, cells = _shared_wall(hall, r)
            for c in cells:
                if c in land:
                    seeds.add(c)
                elif c in fc:
                    for dx, dy in _STEP.values():
                        if (c[0] + dx, c[1] + dy) in land:
                            seeds.add((c[0] + dx, c[1] + dy))
    seen, stack = set(), list(seeds)
    while stack:
        c = stack.pop()
        if c in seen:
            continue
        seen.add(c)
        stack.extend((c[0] + dx, c[1] + dy) for dx, dy in _STEP.values() if (c[0] + dx, c[1] + dy) in land)
    return len(land - seen)


def _reached(hall, flight, room):
    """The ends of `flight` a doorway from `room` into `hall` can reach --
    straight onto that end, or across landing floor of the hall (the sensible
    check's `stair_climbable`, read the same way)."""
    from world.layout_solver import _shared_wall
    side, cells = _shared_wall(hall, room)
    if side is None:
        return set()
    hc = hall.cells()
    fc = flight.cells()
    ends = _flight_ends(flight)
    got = set()
    for b, end in ends.items():
        for c in cells:
            if c in end:
                got.add(b)
                break
            if c in fc:
                continue
            seen, stack = set(), [c]
            while stack:
                q = stack.pop()
                if q in seen or q not in hc or q in fc:
                    continue
                seen.add(q)
                stack.extend((q[0] + dx, q[1] + dy) for dx, dy in _STEP.values())
            if any((q[0] + dx, q[1] + dy) in end for q in seen for dx, dy in _STEP.values()):
                got.add(b)
                break
    return got


# ---------------------------------------------------------------- the building

def _laid_key(L):
    """A storey as laid, as a key: its outline, rectangles and pads."""
    return (L.outline.x, L.outline.y, L.outline.w, L.outline.d,
            tuple(sorted((k, r.x, r.y, r.w, r.d) for k, r in L.rects.items())),
            tuple(sorted((r.x, r.y, r.w, r.d) for r in L.pads)))


def _distinct(items, laid_of):
    """`items` (in order) without those laid exactly as an earlier one: the
    ways round a storey's flights often lay it the same, and each copy would
    carry a whole beam of storeys again."""
    seen, out = set(), []
    for it in items:
        key = _laid_key(laid_of(it))
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


@dataclass
class _Laid:
    """One storey as laid: its outline, every leaf's rectangle, its roof
    strips, its cost and what gave way."""
    level: int
    outline: Rect
    rects: dict
    pads: list
    cost: float
    warnings: list = field(default_factory=list)
    penalty: float = 0.0            # asks given way, floor not under it, footprint left
    gave: tuple = ()                # the classes of the asks it gave way (RELAX_ORDER)
    dropped: frozenset = frozenset()  # every ask it gave way, those resolved before laying too
    ledge: float = 0.0              # of `cost`, what its ledges of roof cost (LEDGE_COST; `_weigh`)
    ends: tuple = ()                # a first storey's: the ends of its flights it was laid for (`_end_combos`)


@dataclass
class _State:
    """One carried way of laying a block's storeys so far: its total cost,
    the storeys laid, the flights fixed, and for each shaft the storey that
    fixed it with the ends of the flight its room reaches there."""
    total: float
    storeys: dict
    flights: dict
    reach: dict


@dataclass
class _Edge:
    """A relation the plan asks of two leaves: `side` (the bit of `a`'s side
    `b` lies on), `kind` ("stair", "order" or "side"), and `adj` (they share
    a wall)."""
    a: str
    b: str
    side: int | None
    kind: str
    adj: bool
    why: str = ""


class _Building:
    """The whole building: its blocks, their storeys, laid stepwise."""

    def __init__(self, p):
        self.p = p
        self.rooms = p.rooms
        self.every = p.every
        self.layout = p.layout
        self.front = p.front
        spec = p.spec
        self.smaller = {int(s.get("level") or 0) for s in spec.get("storeys") or ()
                        if isinstance(s, dict) and s.get("smaller")}
        self.declared = {str(b.get("id")): b for b in spec.get("blocks") or ()
                         if isinstance(b, dict) and b.get("id")}
        self.levels = {}
        for r in self.rooms.values():
            self.levels.setdefault(r["block"], set()).add(r["level"])
        self.shafts = {sh.id: sh for sh in p.shafts}
        self.hall_ids = set(p.halls)
        self.warnings = []
        # blocks standing only below the ground (a cavern), and the side of
        # the block they open from each stands on once that block is laid
        # (`_cave_side`): {block: (anchor block, side)}
        self.below_only = {b for b, lvs in self.levels.items() if lvs and max(lvs) < 0}
        self.side_override = {}
        self.large = False              # the block being laid is large (`lay_block`)
        # the work done, counted (`_Meter`): a storey problem laid is let go
        # -- its pinned DP's tables with it -- and only its count kept (every
        # one kept for the count held the unseen inn's 0.87 GB)
        self.meter = _Meter()
        self._families = {}             # storeys alike but for their pins share tables (`make`)
        self._narrow_try = False        # a try searched as a large storey is (`_relaxed`'s climb floor)
        self._strict = False            # storeys laid on a notched ground give nothing way (`_carry`)
        ent = (p.entrance or {}).get("room")
        self.home = self.rooms[ent]["block"] if ent in self.rooms else \
            max(sorted(self.levels), key=lambda b: sum(1 for r in self.rooms.values() if r["block"] == b))

    @property
    def work(self):
        """Table entries built so far, over every storey problem: the
        building's deterministic measure of the time it has taken."""
        return self.meter.total

    # -- what a storey holds ---------------------------------------------------

    def leaves_of(self, b, lv):
        rooms = sorted(rid for rid, r in self.rooms.items() if r["block"] == b and r["level"] == lv)
        halls = sorted(f"{sh.id}@{lv}" for sh in self.p.shafts if sh.block == b and lv in sh.levels)
        return rooms + halls

    def _room_leaf(self, rid, lv):
        r = self.rooms[rid]
        key = purpose_key(r)
        stated = _stated_area(r)
        target = stated or room_target(r, stated=False)
        if key in CORRIDORS:
            return Leaf(rid, "corridor", target=target, hint=max(target, 8.0))
        lo, hi = PURPOSE_AREA[key]
        needs = []
        for fx in r.get("fixtures") or ():
            at = str(fx.get("at") or "").casefold()
            a, bb = _use_need(fx)
            ap, bp = _use_need(dict(fx, size=None)) if fx.get("size") else (a, bb)
            needs.append((a, bb, at if at in _SIDES else "", ap, bp))
        return Leaf(rid, "room", target=target, flexible=key in FLEXIBLE,
                    need=room_target(r, stated=False),
                    size_kind="stated" if stated else ("flex" if key in FLEXIBLE else "keep"),
                    ceiling=max(hi, target) * MAX_GROWTH,
                    min_side=MIN_SIDE_SMALL if key in SMALL_PURPOSES else MIN_SIDE_ROOM,
                    needs=tuple(needs), under_roof=lv > 0 and lv in self.smaller, hint=target)

    def _hall_leaf(self, hid, kind, pin, dropped=frozenset()):
        sh = self.shafts[hid.rsplit("@", 1)[0]]
        fw, fd = STAIRS[kind]
        long_, short = max(fw, fd), min(fw, fd)
        # the walls its rooms ask the flight along, on every storey it climbs
        # -- save a wall THIS storey gave way: the flight then runs as the
        # asks still in force allow (the code review's finding 6: a cellar
        # stair asked only on the entrance's front wall gave that wall way,
        # still ran east-west, and turned the kitchen asked north as well)
        walls = {st.at.get(rid) for st in sh.flights for rid in (st.low, st.high)
                 if frozenset((hid, rid)) not in dropped} - {None}
        if long_ == short:
            flights, run = ((fw, fd),), None
        elif walls and walls <= {"n", "s"}:
            flights, run = ((long_, short),), "ew"      # along a north or south wall
        elif walls and walls <= {"e", "w"}:
            flights, run = ((short, long_),), "ns"
        else:
            flights, run = ((long_, short), (short, long_)), None
        bw, bd = Leaf._hall_base(*flights[0])
        return Leaf(hid, "hall", run=run, flights=flights, pin=pin, shaft=sh.id, hint=float(bw * bd))

    def _first(self, b):
        """The storey of block `b` laid first: the ground, else the storey
        nearest it (`lay_block`)."""
        levels = self.levels[b] | {lv for sh in self.p.shafts if sh.block == b for lv in sh.levels}
        return 0 if 0 in levels else min(levels, key=lambda v: (abs(v), v))

    def _window_landing(self, hid, lv):
        """The landing along its run hall `hid` gives on storey `lv`, where
        that storey lays its flight first, so that a room on the storey
        above asking a window on the wall the flight arrives along can run
        past the flight's end onto roof: one cell a window, at most
        LANDING_MAX (`WINDOW_LANDING_COST`). Above the ground only: at or
        below it a window beats the stair's wall outright (`storey`)."""
        sh = self.shafts[hid.rsplit("@", 1)[0]]
        nxt = lv + 1
        if nxt not in sh.levels or nxt <= 0:
            return 0
        n = 0
        for st in sh.flights:
            for rid in (st.low, st.high):
                at = st.at.get(rid)
                if self.rooms[rid]["level"] != nxt or not at:
                    continue
                for wdef in self.rooms[rid].get("windows") or ():
                    if isinstance(wdef, dict) and str(wdef.get("side") or "")[:1] == at:
                        try:
                            n += max(1, min(8, int(wdef.get("count") or 1)))
                        except (TypeError, ValueError):
                            n += 1
                        # ...AND THE FLOOR THING THE PLAN SETS BY THAT WINDOW
                        # (the review's visual 4): one cell a window put the
                        # window beside the stair's arrival door, the desk
                        # asked beneath it standing elsewhere (1 of 2 roosts
                        # asking it); its width too, it stood beneath the
                        # window in 2 of 2
                        wid = str(wdef.get("id") or "")
                        n += max((max(fixture_footprint(fx)[:2]) for fx in self.rooms[rid].get("fixtures") or ()
                                  if wid and str(fx.get("near") or "") == wid), default=0)
        return min(n, LANDING_MAX)

    def _block_side(self, b_from, b_to, asked):
        """The side of block `b_from` that block `b_to` stands beyond, as the
        plan places the blocks (`beside`), else the side the join asks -- or,
        for a cavern whose side gave way, the side it stands on
        (`_cave_side`)."""
        got = self.side_override.get(b_to)
        if got is not None and got[0] == b_from:
            return got[1]
        got = self.side_override.get(b_from)
        if got is not None and got[0] == b_to:
            return _OPP[got[1]]
        decl = self.declared.get(b_to) or {}
        bes = decl.get("beside") or {}
        default = {"n": "e", "s": "e", "e": "n", "w": "n"}[self.front]
        if bes.get("block") == b_from or (not bes and b_from == self.home):
            sd = str(bes.get("side") or "")[:1]
            return sd if sd in _SIDES else default
        decl = self.declared.get(b_from) or {}
        bes = decl.get("beside") or {}
        if bes.get("block") == b_to or (not bes and b_to == self.home):
            sd = str(bes.get("side") or "")[:1]
            return _OPP[sd if sd in _SIDES else default]
        return asked

    def relations(self, b, lv, ids):
        """Every relation the plan asks among one storey's leaves, as edges,
        and its demands: the outline sides its rooms must reach (doors
        outdoors on the ground, the entrance on the front, a block beyond),
        the sides its windows ask, and the rooms that open outdoors on no
        named side."""
        here = set(ids)
        edges = {}
        for a in ids:
            for other, (side, _order, _kind) in _joins(a, self.every).items():
                if other not in here:
                    continue
                key = frozenset((a, other))
                stair = a in self.hall_ids or other in self.hall_ids
                bit = _BIT.get(side) if side else None
                e = edges.get(key)
                if e is None:
                    edges[key] = _Edge(a, other, bit, "stair" if stair else "side", True)
                elif bit and e.side is None:
                    edges[key] = _Edge(a, other, bit, e.kind, True)
                elif bit and e.side is not None:
                    want = e.side if e.a == a else _OPPBIT[e.side]
                    if want != bit:
                        self.warnings.append(f"{self.layout.names.get(a, a)} and {self.layout.names.get(other, other)}"
                                             f" are asked on two sides of each other; the first asked holds")
        # ordered joins along one wall: each next one lies further from the
        # wall's north or west end
        for a in ids:
            r = self.rooms.get(a)
            if r is None:
                continue
            by_side = {}
            for j in r.get("joins") or ():
                to, sd, od = j.get("to"), str(j.get("side") or "")[:1], j.get("order")
                if to in here and to != a and sd in _SIDES and isinstance(od, (int, float)) \
                        and not isinstance(od, bool):
                    by_side.setdefault(sd, []).append((od, to))
            for sd, lst in sorted(by_side.items()):
                lst.sort()
                step = 4 if sd in "ew" else 2
                for (_o1, x1), (_o2, x2) in zip(lst, lst[1:]):
                    key = frozenset((x1, x2))
                    if key not in edges:
                        edges[key] = _Edge(x1, x2, step, "order", False, why=a)
        demand, wish, wish_any, why, need = {}, {}, set(), {}, {}
        cave, cave_any = {}, set()
        below = lv < self._first(b)
        for a in ids:
            r = self.rooms.get(a)
            if r is None:
                continue
            # every side the room opens outdoors on (`_prepare`'s `outward`
            # keeps one a room): the entrance on the front, each door asked
            want = self.p.outward.get(a)
            sides = {str(j.get("side") or "")[:1] for j in r.get("joins") or ()
                     if j.get("to") in self.p.outdoor_ids} & set(_SIDES)
            if want in _SIDES:
                sides.add(want)
            if lv == 0:
                for sd in sorted(sides):
                    demand[a] = demand.get(a, 0) | _BIT[sd]
                    why.setdefault(a, {})[_BIT[sd]] = "door"
                if want == "any" and not sides:
                    wish_any.add(a)
            else:
                for sd in sorted(sides):
                    wish[a] = wish.get(a, 0) | _BIT[sd]
                    need[(a, _BIT[sd])] = need.get((a, _BIT[sd]), 0) + 1
            for other, (side, _o, _k) in _joins(a, self.rooms).items():
                ob = self.rooms[other]["block"]
                if ob == b or self.rooms[other]["level"] != lv:
                    continue
                sd = self._block_side(b, ob, side)
                if below and ob in self.below_only and b not in self.below_only:
                    # A CAVERN BESIDE A STOREY BELOW THE GROUND: that storey
                    # lies under the house, so the cavern's side is asked,
                    # not demanded -- a stair or a room the plan asks on that
                    # wall keeps it, and the cavern stands beyond another
                    # wall the room leaves exposed (`_cave_side`)
                    if sd in _SIDES:
                        cave[a] = cave.get(a, 0) | _BIT[sd]
                    cave_any.add(a)
                    continue
                if sd in _SIDES:
                    demand[a] = demand.get(a, 0) | _BIT[sd]
                    why.setdefault(a, {})[_BIT[sd]] = "block"
            for wdef in r.get("windows") or ():
                if isinstance(wdef, dict):
                    sd = str(wdef.get("side") or "")[:1]
                    if sd in _SIDES:
                        wish[a] = wish.get(a, 0) | _BIT[sd]
                        # one cell of outside wall for each window of the
                        # record (`_place_windows` lays `count`, one a cell)
                        n = max(1, min(8, int(wdef.get("count") or 1)))
                        # ...and, above the ground, the floor thing the plan
                        # sets by it beneath it: a room running past a stair
                        # hall's end onto roof runs as far as the landing
                        # below gives (`_window_landing`, at most
                        # LANDING_MAX), or the thing stood beside the window
                        # (the review's visual 4)
                        wid = str(wdef.get("id") or "")
                        wide = max((max(fixture_footprint(fx)[:2]) for fx in r.get("fixtures") or ()
                                    if lv > 0 and wid and str(fx.get("near") or "") == wid), default=0)
                        if wide:
                            n = min(n + wide, max(n, LANDING_MAX))
                        need[(a, _BIT[sd])] = need.get((a, _BIT[sd]), 0) + n
        return edges, demand, wish, wish_any, why, need, cave, cave_any

    # -- one storey ------------------------------------------------------------

    def _corridor_runs(self, ids, edges):
        """{corridor: "ns" | "ew" | None}: A CORRIDOR RUNS PAST THE ROOMS IT
        SERVES -- rooms off its east or west side make it run north-south
        (the owner's default: "corridors take their axis from their joins")."""
        runs = {}
        for x in ids:
            if x in self.hall_ids or purpose_key(self.rooms[x]) not in CORRIDORS:
                continue
            ew = ns = 0
            for key, e in edges.items():
                if x not in key or e.side is None or e.kind != "side":
                    continue
                if e.side & _EW:
                    ew += 1
                else:
                    ns += 1
            runs[x] = "ns" if ew > ns else ("ew" if ns > ew else None)
        return runs

    def storey(self, b, lv, ids, pins, dropped, hall_end, kinds, earth=False, keeps=None, whole=False):
        """The DP problem for one storey: leaves and relations, with the asks
        in `dropped` (edge keys, ("end", hall), ("adj", a, b) or ("door",
        room, side bit)) given way. Returns its parts, the notes on the
        contradictions it resolved before laying, and `dropped` with those."""
        edges, demand, wish, wish_any, why, need, cave, cave_any = self.relations(b, lv, ids)
        # A DOOR OUTDOORS GIVEN WAY (RELAX_ORDER's last, "door") no longer
        # holds its room to that side of the outline: the lab's doors turn
        # it, and say so (`layout_solver._place_doors`)
        for key in dropped:
            if isinstance(key, tuple) and key[0] == "door" and key[1] in demand:
                demand[key[1]] &= ~key[2]
                if not demand[key[1]]:
                    del demand[key[1]]
        runs = self._corridor_runs(ids, edges)
        notes = []
        # A ROOM THAT MUST REACH A SIDE OF THE OUTLINE CANNOT HAVE A NEIGHBOUR
        # ASKED ON THAT SAME SIDE: on a rectangular storey the neighbour would
        # stand outside it (the lab shrine's main hall, a garden door and the
        # kitchen both asked east; a cellar stair asked on the wall its cavern
        # stands beyond). The door outdoors, the entrance and the block beyond
        # are kept; the neighbour's side gives way.
        for key, e in sorted(edges.items(), key=lambda t: sorted(t[0])):
            if e.side is None or key in dropped:
                continue
            for a, b2, bit in ((e.a, e.b, e.side), (e.b, e.a, _OPPBIT[e.side])):
                if demand.get(a, 0) & bit:
                    dropped = dropped | {key}
                    what = why.get(a, {}).get(bit, "door")
                    notes.append((e.kind, a, b2, bit, what))
                    break
        # A CAVERN ASKED BEYOND A WALL OF A ROOM BELOW THE GROUND TAKES THAT
        # WALL FROM A STAIR THE PLAN ASKS ON IT (the fix round's phase 3): a
        # storey below the ground is dug, not built (`EARTH_COST`), so its
        # room can stand beside the stair's hall and reach the outline there,
        # the flight along its side, and the cavern stands beyond the wall
        # the plan puts it -- as the owner's liked lab shrine stands, its
        # basement beside its stair, the seal cavern beyond its north wall.
        # Kept by the stair, the cavern turned in 7 of 14 shrine runs, every
        # one whose plan asked the cellar stair on the basement's north wall
        # too (the stepwise lane's demand had made the storey stand beyond
        # its flight; dug, it need not)
        for key, e in sorted(edges.items(), key=lambda t: sorted(t[0])):
            if e.side is None or key in dropped or e.kind != "stair":
                continue
            for a, b2, bit in ((e.a, e.b, e.side), (e.b, e.a, _OPPBIT[e.side])):
                if cave.get(a, 0) & bit:
                    dropped = dropped | {key}
                    notes.append((e.kind, a, b2, bit, "cavern"))
                    break
        # A WINDOW ON THE GROUND (OR BELOW IT) LOOKS OUT ONLY FROM A WALL ON
        # THE OUTLINE: such a storey is one rectangle wholly floor, so a
        # neighbour asked on the same side of the room -- a join's side, an
        # order along the wall, a stair's wall -- leaves that wall inside the
        # building and the window nowhere (the lab's run 2: the kitchen asked
        # on the main hall's east, its one window east too, and the hall laid
        # with no window at all). The owner's order keeps the window over all
        # three; the neighbour's side gives way. Above the ground a roof
        # beside the neighbour can keep both (`_wins`).
        if lv <= 0:
            for key, e in sorted(edges.items(), key=lambda t: sorted(t[0])):
                if e.side is None or key in dropped:
                    continue
                for a, b2, bit in ((e.a, e.b, e.side), (e.b, e.a, _OPPBIT[e.side])):
                    if wish.get(a, 0) & bit:
                        dropped = dropped | {key}
                        notes.append((e.kind, a, b2, bit, "window"))
                        break
        # A CORRIDOR'S END HOLDS ITS STAIR OR A ROOM, NOT BOTH: the end is
        # CORRIDOR_WIDTH paces, and a stair hall asked there takes it -- its
        # room must reach the flight's end along it -- so a room asked on the
        # same end of the same corridor gives way, before laying, with a note
        # (the unseen merchant's house: the maids' room and the gallery stair
        # both asked on the gallery's two-pace west end; that one ask, left
        # to the search, gave every class of ask away and wrote the upper
        # floor unreachable; with the room's side given way first the same
        # search laid the storey correctly in 0.4 s)
        for c, run in sorted(runs.items()):
            if run is None:
                continue
            for end in ((1, 4) if run == "ns" else (8, 2)):
                on_end = []
                for key, e in sorted(edges.items(), key=lambda t: sorted(t[0])):
                    if c not in key or e.side is None or key in dropped:
                        continue
                    other, bit = (e.b, e.side) if e.a == c else (e.a, _OPPBIT[e.side])
                    if bit == end:
                        on_end.append((key, other))
                halls = [o for _k, o in on_end if o in self.hall_ids]
                if not halls:
                    continue
                sid = halls[0].rsplit("@", 1)[0]
                stair = self.shafts[sid].name or "its stair"
                for key, other in on_end:
                    if other not in self.hall_ids:
                        dropped = dropped | {key}
                        notes.append(("side", c, other, end, stair))
        leaves, index = [], {}
        for x in ids:
            if x in self.hall_ids:
                lf = self._hall_leaf(x, kinds[self.p.halls[x]["shaft"]], pins.get(x), dropped)
                # ABOVE THE GROUND A PINNED HALL IS ITS FLIGHT: roof fills its
                # band, and a room beside it then always stands along the
                # flight itself, never along a landing only (the sensible
                # check's 'along': a hallway two paces wide met a landing and
                # 0 of the 5-pace run, on 8 of 18 shrines)
                lf.landing = lv <= 0 or lf.pin is None
                # BELOW THE GROUND a pinned flight may land beside its run
                # (ACROSS_LANDING), for a room at its other end
                lf.across = ACROSS_LANDING if lv < 0 and lf.pin is not None else 0
                if lf.pin is None:
                    lf.min_landing = self._window_landing(x, lv)
                elif lv > 0:
                    # the landing its hall below took beside the run, kept
                    # (KEPT_LANDING_COST) -- whole on a storey of one room
                    # that rises sheer (`_sheer_box`)
                    lf.keep = (keeps or {}).get(x)
                    lf.whole = whole and lf.keep is not None
            else:
                lf = self._room_leaf(x, lv)
                lf.dug = earth
                if lf.kind == "corridor":
                    lf.run = runs.get(x)
            index[x] = len(leaves)
            leaves.append(lf)
        orient, adj = {}, []
        for key, e in sorted(edges.items(), key=lambda t: sorted(t[0])):
            i, j = index[e.a], index[e.b]
            if e.adj and ("adj",) + tuple(sorted(key)) not in dropped:
                adj.append((min(i, j), max(i, j)))
            if e.side is not None and key not in dropped:
                orient[(i, j)] = e.side
                orient[(j, i)] = _OPPBIT[e.side]
        serves = {}
        for x in ids:
            if x in self.hall_ids:
                serves[index[x]] = [index[j["to"]] for j in self.p.halls[x]["joins"] if j["to"] in index]
        ends = {index[h]: bit for h, bit in hall_end.items() if h in index and ("end", h) not in dropped}
        for i, bit in ends.items():
            if leaves[i].pin is not None:
                leaves[i].used_end = bit            # DEAD_LANDING_COST past the other end
        wish_i = {index[a]: m for a, m in wish.items()}
        need_i = {(index[a], bit): n for (a, bit), n in need.items() if index[a] in wish_i}
        dem = {index[a]: m for a, m in demand.items()}
        any_i = {index[a] for a in wish_any}
        cave_i = ({index[a]: m for a, m in cave.items()}, {index[a] for a in cave_any})
        # the outline sides each room must reach for a door outdoors only --
        # not for a building beyond -- where a notch may stand before it
        # (`_Storey._notch_sides`)
        doors_i = {}
        for a, m in demand.items():
            for bit in (1, 2, 4, 8):
                if m & bit and why.get(a, {}).get(bit) == "door":
                    doors_i[index[a]] = doors_i.get(index[a], 0) | bit
        return (leaves, index, orient, adj, dem, wish_i, any_i, serves, ends, notes, edges, need_i, cave_i, doors_i,
                dropped)

    def make(self, b, lv, ids, pins, dropped, hall_end, kinds, pad, M, earth=False, keeps=None, over=None,
             whole=False, notch=frozenset(), step_cost=NOTCH_STEP_COST):
        """The DP problem of one storey (`storey`), as a _Storey. Storeys
        that differ only in where their pinned flights stand -- the same
        storey laid on another carried state -- share every table but the
        pinned DP's: what a set of leaves costs in a w x h, its cuts and its
        bounds do not depend on where a flight stands."""
        leaves, index, orient, adj, dem, wish, any_i, serves, ends, notes, edges, need, (cave, cave_any), doors, \
            held = self.storey(b, lv, ids, pins, dropped, hall_end, kinds, earth, keeps, whole)
        # ON A STOREY LAID WHOLLY FLOOR a hall may take a landing past its
        # cap, priced (LANDING_OVER_COST): nothing but a leaf fills its band
        # -- save on a large storey, searched narrowly: there the landing
        # moved the few cuts read, and the unseen hospital's upper floor
        # found no layout on any ground so laid (searched wide, the same
        # ground lays both storeys giving nothing way, in 6 to 23 s against
        # 4.5 s)
        wide = len(leaves) <= LARGE_STOREY and len(self.rooms) <= LARGE_BUILDING
        for lf in leaves:
            lf.over = lf.kind == "hall" and lf.pin is None and pad is None and not earth and wide
        # THE GROUND, ITS OUTLINE FREE TO STEP (`NOTCH_COST`) in the slots
        # of the rooms `notch` names, and its heart rooms, which keep a wall
        # to the outside (`HEART_DARK_COST`)
        notch = frozenset(x for x in notch if x in index and x in self.rooms and x not in self.hall_ids)
        heart = frozenset(index[x] for x in ids if notch and x in self.rooms and x not in self.hall_ids
                          and purpose_key(self.rooms[x]) in HEART_PURPOSES)
        st = _Storey(leaves, orient, adj, dem, wish, any_i, ends, pad, M, serves, need=need,
                     cave=cave, cave_any=cave_any, earth=earth, meter=self.meter, level_key=(b, lv),
                     over={index[r]: rects for r, rects in (over or {}).items() if r in index},
                     notch=frozenset(index[x] for x in notch), heart=heart)
        st.doors = doors if notch else {}
        st.step_cost = step_cost
        # NARROW_WORK is counted per storey (`_Meter.by_storey`), and checked
        # as each table is built too (`_Storey._tick`)
        narrow = self.meter.by_storey.get((b, lv), 0) > st.narrow_at or len(self.rooms) > LARGE_BUILDING or \
            self._narrow_try
        if narrow and not st.narrowed:
            st._narrow()
        narrow = st.narrowed
        # the asks given way -- those resolved before laying too -- as the
        # tables read them (`_Storey._drops_of`): each a key, the leaves it
        # holds, and its hall where a stair's wall gives way
        masks = []
        for key in sorted(held, key=lambda k: sorted(map(str, k))):
            if isinstance(key, frozenset):
                a_, b_ = sorted(key)
                i, j = sorted((index[a_], index[b_]))
                hall = sum(1 << index[x] for x in key if x in self.hall_ids)
                masks.append((("e", i, j), (1 << i) | (1 << j), hall))
            elif key[0] == "adj":
                i, j = sorted((index[key[1]], index[key[2]]))
                masks.append((("a", i, j), (1 << i) | (1 << j), 0))
        st.drop_masks = tuple(masks)
        # neither the ends asked of the flights nor the asks given way are in
        # the key: a table reads them only for a set holding the leaves they
        # name, and is keyed by those (`_Storey._sig`), so the storey laid
        # each way round its flights, and each try of it with other asks
        # given way, share every other table
        # ...and the shapes its stairs are laid as (`_climb` lays a block
        # again with a flight turned: no table of the straight one is read)
        family = (b, lv, tuple(ids), pad, earth, M, narrow, tuple(sorted(notch)), step_cost if notch else None,
                  tuple(sorted(pins)), tuple(sorted((k, (r.w, r.d)) for k, r in pins.items())),
                  tuple(sorted(kinds.items())),
                  tuple(sorted((k, s) for k, s in ((k, self._kept_key(k, r, pins)) for k, r in (keeps or {}).items())
                               if s is not None)))
        shared = self._families.get(family)
        if shared is None:
            self._families[family] = (st._tables, st._cuts, st._leaf_tables)
        else:
            st._tables, st._cuts, st._leaf_tables = shared
        # what this storey gave way, those resolved before laying included:
        # the flight's walls read it again where it is fixed (`_fix_flight`)
        st.dropped = held
        return st, index, notes, edges

    @staticmethod
    def _kept_key(hid, keep, pins):
        """What of the hall below a pinned hall's tables read (`_kept`): its
        extent across the run, or both extents for a stair with none; None
        where it keeps nothing past its least hall -- so storeys laid on
        carried states whose halls below differ only along the run share
        their tables, as before the kept landing (`make`)."""
        f = pins.get(hid)
        if keep is None or f is None:
            return None
        bw, bd = Leaf._hall_base(f.w, f.d)
        if max(f.w, f.d) >= STRAIGHT_RUN and f.w != f.d:
            across = keep.d if f.w > f.d else keep.w
            return across if across > (bd if f.w > f.d else bw) else None
        return (keep.w, keep.d) if (keep.w, keep.d) != (bw, bd) else None

    def _relaxations(self, b, lv, ids, edges, pins, hall_end, demand, why):
        """The asks a storey that cannot hold them all gives way, lowest
        first, each a list of drop keys tried one after another: the shared
        walls only on the storey laid first (GROUND_ONLY), a door outdoors
        last (`_door_keys`)."""
        out = []
        ground = lv == self._first(b)
        pinned = set()
        for cls in RELAX_ORDER:
            if cls in GROUND_ONLY and not ground:
                continue
            if cls == "stair_pinned":
                keys = [k for k, e in edges.items() if e.kind == "stair" and e.side is not None
                        and any(x in pins for x in k)]
                pinned = set(keys)
            elif cls in ("stair", "order", "side"):
                # a pinned stair's wall is given way once, in its own class
                # (it was counted under both, and tried twice)
                keys = [k for k, e in edges.items() if e.kind == cls and e.side is not None and k not in pinned]
            elif cls == "way":
                keys = [("end", h) for h in sorted(hall_end) if h not in pins]
            elif cls == "end":
                keys = [("end", h) for h in sorted(hall_end) if h in pins]
            elif cls == "landed":
                keys = [("adj",) + tuple(sorted(k)) for k, e in edges.items() if e.adj and e.kind == "stair"]
            elif cls == "join":
                keys = [("adj",) + tuple(sorted(k)) for k, e in edges.items() if e.adj and e.kind != "stair"]
            else:
                out.append((cls, self._door_keys(ids, demand, why)))
                continue
            out.append((cls, sorted(keys, key=lambda k: sorted(map(str, k)))))
        return out

    def _door_keys(self, ids, demand, why):
        """THE DOOR-TURN TIER (the code review's finding 1: a hall with doors
        outdoors on three sides beside a kitchen with a door onto the same
        yard raised, where the lab turns one door and says so): every side a
        room must reach for a door outdoors, as a key ("door", room, side
        bit) -- never the entrance's own front -- the lowest first: a door of
        a room other than the entrance's, then one onto a place another door
        reaches too, then one onto a thing at a door; ties by room and side."""
        ent = (self.p.entrance or {}).get("room")
        front = _BIT.get(self.front)
        reach = {}
        for a in ids:
            r = self.rooms.get(a)
            if r is None:
                continue
            for j in r.get("joins") or ():
                t = j.get("to")
                if t in self.p.outdoor_ids:
                    reach.setdefault(t, set()).add((a, _BIT.get(str(j.get("side") or "")[:1], 0)))
        ranked = []
        for a, m in sorted(demand.items()):
            for bit in (1, 2, 4, 8):
                if not m & bit or why.get(a, {}).get(bit) != "door" or (a == ent and bit == front):
                    continue
                targets = sorted(t for t, rs in reach.items() if (a, bit) in rs)
                shared = bool(targets) and all(reach[t] - {(a, bit)} for t in targets)
                thing = any(t in self.p.things for t in targets)
                ranked.append(((a == ent, not shared, not thing, a, bit), ("door", a, bit)))
        return [k for _r, k in sorted(ranked)]

    def _conflicted(self, edges, held, runs):
        """The asks in a contradiction found before laying, given way first
        within their class: every side or order on a cycle of sides along
        one axis (no cut can ever part it), and every leaf past the second
        asked on one end of a corridor (CORRIDOR_WIDTH paces hold two)."""
        out = set()
        for fwd, back in ((2, 8), (4, 1)):
            graph = {}
            for key, e in edges.items():
                if e.side is None or key in held:
                    continue
                if e.side == fwd:
                    graph.setdefault(e.a, []).append((e.b, key))
                elif e.side == back:
                    graph.setdefault(e.b, []).append((e.a, key))

            def reaches(src, dst):
                seen, stack = set(), [src]
                while stack:
                    u = stack.pop()
                    if u == dst:
                        return True
                    if u in seen:
                        continue
                    seen.add(u)
                    stack.extend(v for v, _k in graph.get(u, ()))
                return False

            for u, lst in graph.items():
                for v, key in lst:
                    if reaches(v, u):
                        out.add(key)
        for c, run in runs.items():
            if run is None:
                continue
            for end in ((1, 4) if run == "ns" else (8, 2)):
                on_end = [key for key, e in edges.items() if c in key and e.side is not None and key not in held
                          and (e.side if e.a == c else _OPPBIT[e.side]) == end]
                if len(on_end) > 2:
                    out.update(on_end)
        return out

    def _note(self, cls, key, edges):
        """A sentence for an ask that gave way; None for a door outdoors, which
        the lab's doors turn and name themselves (`_place_doors`)."""
        name = self.layout.names
        if cls in ("door", "way"):
            # a door turned is named by the lab's doors; the end a storey
            # laying a flight first reaches is the core's own choice, laid
            # both ways round -- the climb is judged on the whole block
            # (`_unclimbed`)
            return None
        if cls in ("landed", "join"):
            a, b = key[1], key[2]
            return (f"{name.get(a, a)} and {name.get(b, b)} could not share a wall: the storey cannot hold "
                    f"every join the plan asks")
        if cls == "end":
            return f"{name.get(key[1], key[1])}: its room could not reach the end of the flight its storey takes"
        e = edges[key]
        a, b = e.a, e.b
        if e.kind == "order":
            return (f"{name.get(a, a)} and {name.get(b, b)} could not stand in the order asked along "
                    f"{name.get(e.why, e.why)}'s wall")
        side = _SIDE_OF.get(e.side, "?")
        if e.kind == "stair":
            hall, room = (a, b) if a in self.hall_ids else (b, a)
            side = _SIDE_OF.get(e.side if room == a else _OPPBIT[e.side], "?")
            return (f"{name.get(hall, hall)} could not stand at {name.get(room, room)}'s {side} wall as asked; "
                    f"it stands where the storey allows")
        return (f"{name.get(b, b)} was asked on the {side} side of {name.get(a, a)} and could not stand there; "
                f"it stands where the storey allows")

    # -- laying a storey ---------------------------------------------------------

    def _M_free(self, ids):
        total = 0.0
        for x in ids:
            if x in self.hall_ids:
                total += 14
            else:
                r = self.rooms[x]
                stated = _stated_area(r)
                t = stated or room_target(r, stated=False)
                total += max(t * 1.6, t + 12)
        return max(8, min(48, int(math.ceil(math.sqrt(total) * 2.0)) + 4))

    def lay_free(self, b, lv, ids, kinds, count, hall_end=None, margin=LOOKAHEAD_MARGIN, min_area=0,
                 notch=frozenset(), outlines=(), plain_back=True):
        """The storey laid first in its block (the ground): its outline free,
        one rectangle -- wholly floor, or where `notch` (room ids) its edge
        free to step in those rooms' slots (`NOTCH_COST`). Returns its cheapest `count` layouts by outline,
        [(cost, _Laid)] -- drawn from within `margin` of the cheapest, and,
        where the storeys beside it need more floor than it does
        (`min_area`, LOOKAHEAD_GROW), of outlines that large only; and the
        layout of each of `outlines` [(W, D)] the storey can take."""
        M = self._M_free(ids)
        hall_end = hall_end or {}
        # never on a ground laid larger for the storeys beside it
        # (`min_area`), whose floor is what it is laid for; nor on a ground
        # holding a join between two rooms asked no side: each such join
        # multiplies the ways its search reads (NARROW_WORK_OPEN), and notches
        # multiplied them again (the code review's grids, three rooms by three
        # joined with no side asked: 1.49 M table entries and past a 1.6 GB
        # cap with notches, 0.6 M and 0.68 GB without)
        notched = frozenset(notch) if lv == 0 and not min_area and not self._open_joins(b, lv, ids) else frozenset()

        def attempt(dropped, gave):
            got = laid_as(dropped, gave, notched)
            if got is None or not notched:
                return got
            # A GROUND WHOSE NOTCHES MAKE MORE THAN GROUND_STEPS_MAX REFLEX
            # CORNERS, part its rooms or part two the plan joins is not kept:
            # its outlines are laid again with each reflex corner dearer
            # (NOTCH_RETRY_FACTOR), and failing that as one rectangle wholly
            # floor, beside those that held (a skeleton of the shrine, its
            # heart asked a neighbour on every side, notched four corners
            # deep; laid wholly floor its main hall came out 3 x 3)
            kept = [t for t in got if _stands(t[1]) and self._joins_hold(t[1])]
            if len(kept) == len(got):
                return got
            again = [t for t in laid_as(dropped, gave, notched, NOTCH_STEP_COST * NOTCH_RETRY_FACTOR) or ()
                     if _stands(t[1]) and self._joins_hold(t[1])]
            # ...beside those laid wholly floor, where the caller has none
            # (`plain_back`; `_carry` carries those first)
            plain = [] if again or not plain_back else (laid_as(dropped, gave, frozenset()) or [])
            out = sorted(kept + again + plain, key=lambda t: t[0])
            return out[:max(count, 1)] or None

        def laid_as(dropped, gave, notch, step_cost=NOTCH_STEP_COST):
            st, index, notes, edges = self.make(b, lv, ids, {}, dropped, hall_end, kinds, None, M, notch=notch,
                                                step_cost=step_cost)
            T0 = st.canon(st.demand)
            tab = st.table(st.full, T0, _ALL)
            if not tab.cost:
                return None
            cands = []
            for (W, D, _k), c in tab.cost.items():
                if W * D < min_area:
                    continue
                ar = max(W, D) / min(W, D)
                cands.append((c + OUTLINE_COST * max(0.0, ar - OUTLINE_ASPECT), W, D))
            if not cands:
                return None
            cands.sort()
            # the cheapest outline, then the cheapest of every other depth
            # and every other width the storey can take within LOOKAHEAD_
            # MARGIN of it -- the storeys above may need a deeper or a wider
            # floor than the ground needs for itself
            picked = cands[:1]
            # ...and the outlines asked by size -- those of the grounds laid
            # wholly floor the storeys above were carried on (`_carry`)
            for c, W, D in cands:
                if (W, D) in outlines and (c, W, D) not in picked:
                    picked.append((c, W, D))
            if count > 1:
                best_c = cands[0][0]
                by_d, by_w = {}, {}
                for c, W, D in cands:
                    if c > best_c + margin:
                        break
                    by_d.setdefault(D, (c, W, D))
                    by_w.setdefault(W, (c, W, D))
                # the cheapest of each depth and of each width, taken in turn
                ds, ws = sorted(by_d.values()), sorted(by_w.values())
                for k in range(max(len(ds), len(ws))):
                    for lst in (ds, ws):
                        if k < len(lst) and lst[k] not in picked and len(picked) < count:
                            picked.append(lst[k])
            out = []
            given = sum(RELAX_COST[cls] for cls, _k, _e in gave)
            for c, W, D in picked:
                rects, pads = {}, []
                st.place(st.full, T0, _ALL, 0, 0, W, D, rects, pads)
                named = {ids[i]: r for i, r in rects.items()}
                laid = _Laid(lv, Rect(0, 0, W, D), named, pads, c, self._words(notes, gave, edges, named), given,
                             tuple(cls for cls, _k, _e in gave), st.dropped, ends=tuple(sorted(hall_end.items())))
                out.append((c + given, laid))
            return out

        return self._relaxed(b, lv, ids, {}, hall_end, kinds, attempt) or []

    def _open_joins(self, b, lv, ids):
        """Does the storey hold a join between two rooms the plan asks no
        side of (`_Storey.open_joins`)?"""
        edges = self.relations(b, lv, ids)[0]
        return any(e.side is None and e.adj and e.kind == "side" for e in edges.values())

    def _joins_hold(self, laid):
        """Does every join of the plan between two rooms of this storey that
        it did not give way still share a wall as laid -- a notch never parts
        two rooms the plan joins (`lay_free`'s check of a notched ground)?"""
        for a in sorted(laid.rects):
            if a not in self.rooms:
                continue
            for other in sorted(_joins(a, self.rooms)):
                if other <= a or other not in laid.rects:
                    continue
                if ("adj",) + tuple(sorted((a, other))) in laid.dropped:
                    continue
                if not _door_cells(laid.rects[a], laid.rects[other])[1]:
                    return False
        for hid in laid.rects:
            if hid not in self.hall_ids:
                continue
            for j in self.p.halls[hid]["joins"]:
                r = j["to"]
                if r in laid.rects and ("adj",) + tuple(sorted((hid, r))) not in laid.dropped and \
                        not _door_cells(laid.rects[hid], laid.rects[r])[1]:
                    return False
        return True

    def _relaxed(self, b, lv, ids, pins, hall_end, kinds, attempt):
        """`attempt(dropped, gave)` -> a result, or None where the storey
        cannot be laid so. Tried with every ask; then giving way ONE ASK AT A
        TIME in their order (`_give_way`), each kept given way while the next
        is tried, for RELAX_LINEAR tries; past them THE FLOOR -- every ask
        that may give way given: where the storey does not lay even so, it is
        not laid on this state -- and else the fewest of the order that lay
        it, found by halving (each try is a whole solve). Then EVERY ASK GIVEN WAY BEFORE THE LAST IS GIVEN BACK where
        the storey still lays without it, the latest (the highest in
        RELAX_ORDER) first: the lowest gives way, and only what must.
        Cumulative giving way kept every earlier drop: a cellar stair asked
        on a wall the house's footprint cannot hold gave way only after the
        end of the flight its basement reaches had -- which the basement
        could reach -- and that drop's price (30) chose another ground (the
        merge lane's lm3 clone 172 #1, 2026-10-15). Every ask is tried back,
        on a large storey too (2026-10-19): at most six were, none on a large
        building, and the asks given way earliest -- the windows, once a
        class of their own -- stayed given way. A large storey gave a whole
        class away at a time past eight tries, the guidance its narrow
        search needed with it (the unseen merchant's house), and a storey
        that could not be laid tried every ask before it knew (the unseen
        hospital's upper floor: 21 tries, 14 s, on one carried state)."""
        got = attempt(frozenset(), [])
        if got is not None or self._strict:
            return got
        edges, order = self._give_way(b, lv, ids, pins, hall_end, kinds)
        n = len(order)
        if not n:
            return None
        # THE CLIMB'S OWN FLOOR (`RELAX_ORDER`'s `end`): where the storey does
        # not lay keeping the end its flight is climbed by even with every
        # wish before it given way, the end gives way first -- tried one at a
        # time behind the wishes, it cost the unseen stacked corridors a
        # dozen solves of the storey on every carried state
        at = [j for j, (cls, _k) in enumerate(order) if cls == "end"]
        if at and at[0] > 0:
            # searched narrowly, as a large storey is: the floor only asks
            # whether any giving way keeps the climb, and a storey with every
            # side given way searched wide read every slicing tree of its
            # leaves (the minimal stacked corridors: 0.5 s to 14 s)
            wishes = order[:at[0]]
            self._narrow_try = True
            try:
                floor = attempt(frozenset(key for _c, key in wishes), [(cls, key, edges) for cls, key in wishes])
            finally:
                self._narrow_try = False
            if floor is None:
                order = [order[j] for j in at] + [t for j, t in enumerate(order) if j not in at]

        def prefix(k):
            return (frozenset(key for _c, key in order[:k]),
                    [(cls, key, edges) for cls, key in order[:k]])

        k = got = None
        for j in range(1, min(n, RELAX_LINEAR) + 1):
            g = attempt(*prefix(j))
            if g is not None:
                k, got = j, g
                break
        if got is None:
            if n <= RELAX_LINEAR:
                return None
            # THE FLOOR, past the one-at-a-time tries: every ask that may give
            # way given; where even that does not lay, the storey is not laid
            # on this state -- else the fewest that lay it, by halving
            full = attempt(*prefix(n))
            if full is None:
                return None
            lo, k, got = RELAX_LINEAR, n, full
            while k - lo > 1:
                mid = (lo + k) // 2
                g = attempt(*prefix(mid))
                if g is not None:
                    k, got = mid, g
                else:
                    lo = mid
        dropped, gave = prefix(k)
        for j in range(len(gave) - 2, -1, -1):
            key = gave[j][1]
            d2 = frozenset(dropped - {key})
            g2 = gave[:j] + gave[j + 1:]
            got2 = attempt(d2, g2)
            if got2 is not None:
                dropped, gave, got = d2, g2, got2
        return got

    def _give_way(self, b, lv, ids, pins, hall_end, kinds):
        """`(edges, [(class, key)])`: the asks of a storey that cannot hold
        them all, in the order they give way -- RELAX_ORDER, the shared walls
        on the storey laid first only (GROUND_ONLY) and a door outdoors last;
        within a class, those in a contradiction found before laying first
        (`_conflicted`); an ask the storey resolves before laying anyway left
        out."""
        edges, demand, _wish, _any, why, _need, _cave, _cave_any = self.relations(b, lv, ids)
        held = self.storey(b, lv, ids, pins, frozenset(), hall_end, kinds)[-1]
        conflicted = self._conflicted(edges, held, self._corridor_runs(ids, edges))
        order = []
        for cls, keys in self._relaxations(b, lv, ids, edges, pins, hall_end, demand, why):
            for key in sorted(keys, key=lambda k: k not in conflicted):
                if key not in held:
                    order.append((cls, key))
        return edges, order

    def _holds(self, cls, key, edges, rects):
        """Does an ask given way hold all the same in the storey as laid -- two
        rooms whose shared wall was given way sharing one, a room standing
        on the side asked? Its note would lie (the code review's finding 11:
        'Aa Pantry and Hall could not share a wall' of two rooms sharing the
        hall's east wall)."""
        if cls in ("landed", "join"):
            ra, rb = rects.get(key[1]), rects.get(key[2])
            return bool(ra and rb and _door_cells(ra, rb)[1])
        if cls in ("side", "stair", "stair_pinned"):
            e = edges.get(key)
            ra, rb = (rects.get(e.a), rects.get(e.b)) if e else (None, None)
            if not (ra and rb):
                return False
            got, cells = _door_cells(ra, rb)
            return bool(cells) and got == _SIDE_OF.get(e.side)
        return False

    def _words(self, notes, gave, edges, rects=None):
        """The sentences a storey's layout carries for what it gave way: the
        contradictions resolved before laying, then each ask given way that
        does not hold as laid (`_holds`)."""
        out = []
        name = self.layout.names
        for kind, a, b2, bit, what in notes:
            why = {"door": "its door outdoors", "block": "the building beyond it",
                   "window": "its window", "cavern": "the cavern beyond it"}.get(what, what)
            if kind == "stair":
                hall, room = (a, b2) if a in self.hall_ids else (b2, a)
                out.append(f"{name.get(hall, hall)} could not stand at {name.get(room, room)}'s "
                           f"{_SIDE_OF[bit if room == a else _OPPBIT[bit]]} wall: that wall keeps {why}")
            else:
                out.append(f"{name.get(b2, b2)} was asked on the {_SIDE_OF[bit]} side of {name.get(a, a)}, "
                           f"whose {_SIDE_OF[bit]} wall keeps {why}; it stands elsewhere")
        for cls, key, edges_ in gave:
            if rects is not None and self._holds(cls, key, edges_, rects):
                continue
            words = self._note(cls, key, edges_)
            if words:
                out.append(words)
        return out

    def lay_region(self, b, lv, ids, kinds, pins, hall_end, allowed, box, pad, beyond=None, exact_box=None,
                   count=1, under=None, earth=False, keeps=None, over=None, whole=False):
        """A storey laid inside `allowed` cells (the floor of the storey it
        stands on, or the ground it lies under), on its pinned flights. Its
        outline is a rectangle of `allowed` holding the pins, the cheapest
        first; `beyond` (a Rect) prices every cell of it outside that
        footprint, and `under` (cells) every cell outside those at
        UNDER_COST. `pad` prices a cell of it no room takes -- roof, or
        where `earth` (a storey below the ground) earth; None, none. Returns
        up to `count` layouts [_Laid], cheapest first -- each the best on its
        outline -- or [] when no outline holds it even with every ask that
        may give way given."""
        M = max(box.w, box.d) + 1
        cells = [c for c in allowed if box.x <= c[0] < box.x + box.w and box.y <= c[1] < box.y + box.d]
        floor_box = None
        if cells:
            fx0, fy0 = min(c[0] for c in cells), min(c[1] for c in cells)
            floor_box = (fx0, fy0, max(c[0] for c in cells) + 1 - fx0, max(c[1] for c in cells) + 1 - fy0)
        under_pre = None
        if under is not None:
            under_pre = [[0] * (box.w + 1) for _ in range(box.d + 1)]
            for j in range(box.d):
                row = 0
                for i in range(box.w):
                    row += (box.x + i, box.y + j) in under
                    under_pre[j + 1][i + 1] = under_pre[j][i + 1] + row

        def attempt(dropped, gave):
            st, index, notes, edges = self.make(b, lv, ids, pins, dropped, hall_end, kinds, pad, M, earth, keeps,
                                                over, whole)
            T0 = st.canon(st.demand)
            pin_rects = [lf.pin for lf in st.leaves if lf.pin is not None]
            if exact_box is not None:
                regions = [(exact_box.x, exact_box.y, exact_box.w, exact_box.d)]
            else:
                least = most = 0
                for i in range(st.n):
                    tab = st.leaf_table(i)
                    if not tab:
                        continue
                    floor_c = min(tab.values())
                    least += min(w * h for (w, h) in tab)
                    most += max(w * h for (w, h), c in tab.items() if c <= floor_c + REGION_SPREAD)
                if pad is not None:
                    most = int(most * (1.0 + REGION_ROOF))
                regions = _sub_rects(allowed, box, pin_rects, min_area=least, max_area=max(most, least))
            bound = st.ltable(st.full, T0, _ALL)
            ranked = []
            for (x, y, w, h) in regions:
                lb = bound.get(w, h)
                if lb == INF:
                    continue
                if beyond is not None:
                    inside = max(0, min(x + w, beyond.x + beyond.w) - max(x, beyond.x)) * \
                        max(0, min(y + h, beyond.y + beyond.d) - max(y, beyond.y))
                    add = BEYOND_COST * (w * h - inside)
                else:
                    add = 0.0
                if st.ledge:
                    # the outline set back from the floor below along a
                    # whole wall (`LEDGE_COST`): that strip is roof too
                    add += (st.ledge + pad) * _set_back(allowed, x, y, w, h)
                if under_pre is not None:
                    x0, y0 = x - box.x, y - box.y
                    got = under_pre[y0 + h][x0 + w] - under_pre[y0][x0 + w] - under_pre[y0 + h][x0] + \
                        under_pre[y0][x0]
                    add += UNDER_COST * (w * h - got)
                ranked.append((lb + add, add, y, x, w, h))
            ranked.sort()
            found = []
            tried = 0
            # outlines read cheapest-bound first: once the bound alone of the
            # next passes the `count`-th best found, none after it can enter;
            # and past REGION_TRIES solved, only the floor's own bounding box
            for lb, add, y, x, w, h in ranked:
                if len(found) >= count and lb >= found[-1][0] - 1e-9:
                    break
                if tried >= REGION_TRIES and (x, y, w, h) != floor_box:
                    continue
                tried += 1
                if st.pinned:
                    c = st.G(st.full, T0, _ALL, x, y, w, h, root=True)
                else:
                    c = st.rel_at(st.full, T0, _ALL, (), w, h).get((), (INF,))[0]
                if c == INF:
                    continue
                found.append((c + add, (x, y, w, h)))
                found.sort(key=lambda t: (t[0], t[1][1], t[1][0]))
                del found[count:]
            if not found:
                return None
            out = []
            given = sum(RELAX_COST[cls] for cls, _k, _e in gave)
            for c, (x, y, w, h) in found:
                rects, pads = {}, []
                if st.pinned:
                    st.place_abs(st.full, T0, _ALL, x, y, w, h, rects, pads, root=True)
                else:
                    st.place_at(st.full, T0, _ALL, (), w, h, (), x, y, rects, pads)
                named = {ids[i]: r for i, r in rects.items()}
                L = _Laid(lv, Rect(x, y, w, h), named, pads, c, self._words(notes, gave, edges, named),
                          given, tuple(cls for cls, _k, _e in gave), st.dropped)
                if st.ledge:
                    # what its ledges cost it: the storey's own choice on
                    # this floor, not the ground's (`_weigh`)
                    L.ledge = (st.ledge + pad) * _set_back(allowed, x, y, w, h) + \
                        st.ledge * _pad_ledge(L.outline, named.values())
                out.append(L)
            return out

        return self._relaxed(b, lv, ids, pins, hall_end, kinds, attempt) or []

    # -- the stairs between storeys --------------------------------------------

    def _fix_flight(self, sh, kind, lv, laid):
        """Where the flight stands in its hall on the storey laid first: the
        place in the hall from which the rooms it serves there reach the most
        ends of it, the landing (if any) the rest, where its storey reaches
        it. Returns (flight, ends reached, landing cells sealed)."""
        hid = f"{sh.id}@{lv}"
        H = laid.rects[hid]
        # the flight lies the way its walls ask (`_hall_leaf`) -- those this
        # storey kept -- in whichever of those ways the hall holds it
        shapes = [(w, d) for w, d in self._hall_leaf(hid, kind, None, laid.dropped).flights
                  if w <= H.w and d <= H.d and _hall_past(w, d, H.w, H.d) is not None]
        if not shapes:
            fw, fd = STAIRS[kind]
            shapes = [(w, d) for w, d in ((fw, fd), (fd, fw)) if w <= H.w and d <= H.d]
        served = [j["to"] for j in self.p.halls[hid]["joins"] if j["to"] in laid.rects]
        # the landing a window on the storey above asks (`_window_landing`)
        # is left whole at one end of the flight, for the room there to run
        # past it onto roof
        need = self._window_landing(hid, lv)
        # THE LANDING LIES WHERE ITS STOREY REACHES IT (the review's visual
        # 3): of the places alike in what they keep, the one leaving fewest
        # landing cells that a body reaches only across the flight (`_sealed`)
        # -- the flight placed at the west end of its hall by default, the
        # landing past its far end was sealed in 36 of 40 shrine landings
        straight = kind == "straight"
        enclosed = bool(sh.enclosed)
        best = None
        for w, d in shapes:
            for x in range(H.x, H.x + H.w - w + 1):
                for y in range(H.y, H.y + H.d - d + 1):
                    F = Rect(x, y, w, d)
                    reach = set()
                    along = 0
                    for r in served:
                        reach |= _reached(H, F, laid.rects[r])
                        along += _along(F, laid.rects[r], ALONG_GAP)
                    win = 0
                    if need:
                        ends = ((x - H.x, H.x + H.w - x - w) if w > d else
                                (y - H.y, H.y + H.d - y - d) if d > w else (0, 0))
                        win = -min(need, max(ends))
                    dead = _sealed(H, F, [laid.rects[r] for r in served], reach, enclosed) if straight else 0
                    score = (-along, -len(reach), win, dead, x - H.x, y - H.y)
                    if best is None or score < best[0]:
                        best = (score, F, reach)
        return best[1], best[2], best[0][3]

    def _ends_needed(self, sh, lv, reach, first):
        """The end of the flight the room on storey `lv` must reach, given the
        ends the storey laid first (`first`) reaches: a flight is climbed from
        its foot on its lowest storey to its head on its top one, so the two
        ends of the climb take different ends; a storey between takes
        either."""
        if not reach or len(reach) > 1:
            return None
        low, top = min(sh.levels), max(sh.levels)
        if lv not in (low, top) or first not in (low, top) or lv == first:
            return None
        (only,) = tuple(reach)
        return _OPPBIT[only]

    # -- a block ------------------------------------------------------------------

    def lay_block(self, b):
        """Every storey of block `b`: the first (the ground, else the storey
        nearest it) free; then each storey above on the floor of the one
        below, each below the ground under the one above. A beam: the first
        storey's LOOKAHEAD cheapest outlines are each carried, each storey
        after laid on every carried state in its BEAM_EACH cheapest ways, the
        BEAM cheapest states in all kept. Returns ({level: _Laid}, {shaft:
        (kind, flight)})."""
        levels = sorted(self.levels[b] | {lv for sh in self.p.shafts if sh.block == b for lv in sh.levels})
        first = 0 if 0 in levels else min(levels, key=lambda v: (abs(v), v))
        ups = [lv for lv in levels if lv > first]
        downs = sorted((lv for lv in levels if lv < first), reverse=True)
        kinds = {sh.id: sh.kind for sh in self.p.shafts if sh.block == b}
        tower = b in self.layout.towers and len(levels) > 1
        # WHICH END OF A FLIGHT EACH STOREY TAKES is decided where it binds:
        # the storey that lays a flight first lays it both ways round -- its
        # room reaching the west (or north) end, then the east (or south) --
        # and each way is carried, so the storey the flight climbs to keeps
        # the end its own rooms leave free (the owner's shrine: a hallway
        # with its rooms east keeps the wooden stair's west end, so the main
        # hall below must take the east; and the roof room's stair, laid
        # from the hallway's west end, runs east under the rooms the roof
        # room stands on)
        # A LARGE BUILDING (a storey of more than LARGE_STOREY leaves) is
        # carried narrowly: fewer ground outlines, one layout a storey -- its
        # storeys alone take the tier's time -- but each straight flight
        # still both ways round (`_end_combos`)
        self.large = any(len(self.leaves_of(b, lv)) > LARGE_STOREY for lv in levels)
        best, kinds, notes = self._lay_all(b, first, ups, downs, kinds, tower)
        self.warnings.extend(notes)
        # a block's tables are read by no other block
        self._families = {}
        if best is None:
            raise ValueError(f"block {b}: its storeys could not be laid on any outline of storey {first}")
        return best.storeys, {sid: (kinds[sid], F) for sid, F in best.flights.items()}

    def _lay_all(self, b, first, ups, downs, kinds, tower):
        """The block's storeys (`_lay_kinds`), every straight flight climbed
        (`_climb`). Returns (chain, kinds, sentences)."""
        best, notes = self._lay_kinds(b, first, ups, downs, kinds, tower)
        if best is not None:
            best, kinds, notes = self._climb(b, first, ups, downs, kinds, tower, best, notes)
        return best, kinds, notes

    def _lay_kinds(self, b, first, ups, downs, kinds, tower):
        """The block's storeys with its stairs of `kinds`: the first storey's
        outlines carried with the others (`_carry`), and the ground grown
        where none holds them (LOOKAHEAD_GROW). Returns (the best chain or
        None, the sentences it carries)."""
        notes = []
        combos = self._end_combos(b, first, kinds, set())
        lookahead = LOOKAHEAD_LARGE if self.large else LOOKAHEAD
        best, cheapest, tried = self._carry(b, first, ups, downs, kinds, tower, combos, lookahead,
                                            LOOKAHEAD_MARGIN, set())
        crushed = self._crushed(best, first) if best is not None else []
        if crushed and not self._crowded(best, first, crushed):
            crushed = []                # crushed by how it is arranged, not for floor (CROWDED_SHARE)
        if best is None or self._severe(best, first) or crushed:
            # THE GROUND GROWS ONLY HERE (LOOKAHEAD_GROW): no carried ground
            # held the storeys above it with every room reached -- or with
            # every room the plan sizes at CRUSHED_SHARE of its size at least
            # (the fix round's phase 3: the unseen inn without its office laid
            # Rooms One to Three at 5.1, 5.1 and 6.8 m2 of the 11 stated, its
            # ground's taproom 30% short of its own) -- so the block is laid
            # again on more grounds: the owner's rule yields because the
            # alternative is unreachable or crushed rooms or a refusal
            grow = LOOKAHEAD_GROW if best is None or self._severe(best, first) else LOOKAHEAD_GROW_CRUSHED
            again, _c, _t = self._carry(b, first, ups, downs, kinds, tower, combos, lookahead * grow,
                                        LOOKAHEAD_MARGIN_GROW, tried, self._floor_needed(b, ups + downs, kinds))
            if again is not None and (best is None or not self._severe(again, first) and (
                    self._severe(best, first) or len(self._missed(again)) < len(self._missed(best)))):
                best = again
                g = best.storeys[first]
                if g.cost + g.penalty > cheapest + LOOKAHEAD_MARGIN:
                    notes.append(
                        f"storey {first} was laid larger than its own rooms need: no storey of the size they need "
                        f"could carry the storey{'s' if len(ups + downs) > 1 else ''} beside it with every room "
                        f"reached")
        return best, notes

    def _missed(self, state):
        """Every room of a chain laid off its size past the sensible check's
        own tolerance (1 - CRUSHED_SHARE): a room the plan sizes, either
        way; one it leaves unsized and that may not take spare floor, past
        its target. A ground grown only to spare a storey beside it crushed
        rooms is kept only where it misses fewer (`_lay_kinds`): grown for
        the shrine's clone 168 #2, whose first floor laid Hinami's room at
        half its size, its washroom came out at 50.6 m2, 91% past its
        target."""
        out = []
        tol = 1.0 - CRUSHED_SHARE
        for L in state.storeys.values():
            for rid, r in L.rects.items():
                if rid not in self.rooms or purpose_key(self.rooms[rid]) in CORRIDORS:
                    continue
                t = _stated_area(self.rooms[rid])
                a = r.w * r.d
                if t:
                    if abs(a - t) > tol * t:
                        out.append(rid)
                    continue
                if purpose_key(self.rooms[rid]) not in FLEXIBLE and a > (1.0 + tol) * room_target(
                        self.rooms[rid], stated=False):
                    out.append(rid)
        return sorted(out)

    def _notch_wanted(self, laid):
        """The rooms of the ground laid wholly floor in whose slots a notch
        could buy something -- a room laid past its size band on the large
        side (STATED_BAND for one the plan sizes, KEEP_BAND for one that may
        not take spare floor, or their slack): a notch gives back floor a
        room does not need and never gives one more; and each room beside a
        heart room (HEART_PURPOSES) that has no wall on the outline, whose
        notch would give the heart one. Empty: nothing for a notch to buy.

        A room laid SHORT of its size is no reason (the fix round's phase 3:
        the unseen inn's taproom, laid 70 of a stated 85 cells, and its
        hospital's men's ward, 91 of 107, set the inn and the hospital laying
        their grounds twice, 13.8 s against 5.5 and 9.7 against 6.5, for the
        same layouts)."""
        o = laid.outline
        out = set()
        for rid, r in laid.rects.items():
            room = self.rooms.get(rid)
            if room is None or purpose_key(room) in CORRIDORS:
                continue
            a = r.w * r.d
            t = _stated_area(room)
            if t:
                # a size the plan states, laid past its band
                if math.log(a / t) > math.log(1.0 + max(STATED_BAND, STATED_SLACK / t)):
                    out.add(rid)
            elif purpose_key(room) not in FLEXIBLE:
                k = room_target(room, stated=False)
                if k > 0 and math.log(a / k) > math.log(1.0 + max(KEEP_BAND, KEEP_SLACK / k)):
                    out.add(rid)
            if purpose_key(room) in HEART_PURPOSES and not (
                    r.x == o.x or r.y == o.y or r.x + r.w == o.x + o.w or r.y + r.d == o.y + o.d):
                for oid, q in laid.rects.items():
                    if oid != rid and oid in self.rooms and oid not in self.hall_ids and \
                            purpose_key(self.rooms[oid]) not in CORRIDORS and _walls_meet(r, q):
                        out.add(oid)
        return frozenset(out)

    @staticmethod
    def _wholly_under(state, first, rooms):
        """Does every room of `rooms` on the chain's first storey lie wholly
        under (or over) the rooms and stair halls of the storeys next to it?
        A notch in its slot would leave a room beside it standing over open
        ground, which no storey may (`_lay_next`'s eaves): the notched pass
        could only lay that storey otherwise, and it is laid strictly."""
        g = state.storeys[first]
        cover = set()
        for lv in (first + 1, first - 1):
            L = state.storeys.get(lv)
            if L is not None:
                for r in L.rects.values():
                    cover |= r.cells()
        return all(g.rects[rid].cells() <= cover for rid in rooms if rid in g.rects)

    def _crowded(self, state, first, crushed):
        """Does a storey of the chain holding a room of `crushed` need at
        least CROWDED_SHARE of the first storey's floor -- its rooms at the
        sizes the plan states (else their targets) and its stair halls as
        laid?"""
        floor = sum(r.w * r.d for r in state.storeys[first].rects.values())
        for lv, L in state.storeys.items():
            if lv == first or not any(rid in L.rects for rid in crushed):
                continue
            need = 0.0
            for rid, r in L.rects.items():
                if rid in self.rooms:
                    need += _stated_area(self.rooms[rid]) or room_target(self.rooms[rid], stated=False)
                else:
                    need += r.w * r.d
            if floor and need >= CROWDED_SHARE * floor:
                return True
        return False

    def _crushed(self, state, first):
        """The rooms the plan sizes on the chain's storeys other than the
        first laid at less than CRUSHED_SHARE of that size."""
        out = []
        for lv, L in state.storeys.items():
            if lv == first:
                continue
            for rid, r in L.rects.items():
                # a corridor's length follows its rooms (CORRIDOR_SIZE_W): a
                # size stated of it is no size to keep (the sensible check's
                # own exception; the shrine's clone 174 #2 states its hallway
                # at 12 m2 and lays it at 5.6, as phase 2 did -- read as
                # crushed it grew the ground again for nothing, 2 s to 7)
                if rid not in self.rooms or purpose_key(self.rooms[rid]) in CORRIDORS:
                    continue
                t = _stated_area(self.rooms[rid])
                if t and r.w * r.d < CRUSHED_SHARE * t:
                    out.append(rid)
        return sorted(out)

    def _climb(self, b, first, ups, downs, kinds, tower, best, notes):
        """EVERY STRAIGHT FLIGHT CAN BE CLIMBED, FOOT TO HEAD (the fix
        round's phase 2, 2026-10-19: the unseen plans' finding 4). Where the
        chain laid leaves a straight flight that no body can climb -- the
        rooms it joins on its lowest and top storeys reaching only the same
        end of it (`_unclimbed`) -- the block is laid again with that
        shaft turned back on itself: the next shape of the lab's own
        fallback (`STAIR_FALLBACK`: a U, then a spiral, then a ladder; never
        an L, the owner's ruling of 2026-10-03), whatever shape the plan
        named, and the layout says so. Corridors stacked one over another
        with the stair at their end (the unseen hospital's main stair, laid
        in line with both corridors' west ends; a minimal six-leaf plan)
        meet a straight flight at one end on both storeys wherever it
        stands; a U is climbed from one side, both ends side by side. A
        turn that lays a storey without a shared wall it needs, or does not
        lay, is not taken: the straight flight stays, and the layout says it
        cannot be climbed. Returns (chain, kinds, sentences)."""
        stuck, turned = [], []
        for _round in range(len(kinds)):
            bad = [sid for sid in self._unclimbed(b, best, kinds) if sid not in stuck]
            if not bad:
                break
            sid = bad[0]
            for kind in self._turns(kinds[sid]):
                k2 = dict(kinds)
                k2[sid] = kind
                try:
                    again, n2 = self._lay_kinds(b, first, ups, downs, k2, tower)
                except ValueError:
                    continue
                if again is None or (self._severe(again, first) and not self._severe(best, first)):
                    continue
                best, kinds, notes = again, k2, n2
                turned.append((sid, kind))
                break
            else:
                stuck.append(sid)
        for sid, kind in turned:
            if kinds.get(sid) == kind:
                notes = notes + [f"{self.shafts[sid].name or sid}: a straight flight could not be climbed here -- "
                                 f"the rooms it joins reach the same end of it -- so it turns back on itself, a "
                                 f"{kind} stair"]
        for sid in stuck:
            if sid in self._unclimbed(b, best, kinds):
                notes = notes + [f"{self.shafts[sid].name or sid}: the rooms it joins reach the same end of the "
                                 f"flight; no turning stair fits, and it cannot be climbed foot to head"]
        return best, kinds, notes

    @staticmethod
    def _turns(kind):
        """The shapes a straight flight no body can climb turns to, in the
        lab's own order (`STAIR_FALLBACK`), after `kind`."""
        order = list(STAIR_FALLBACK)
        return order[order.index(kind) + 1:] if kind in order else []

    def _unclimbed(self, b, state, kinds):
        """The straight shafts of block `b` the chain `state` lays that no body
        can climb: no end of the flight that every room it joins on its
        lowest storey reaches (the foot) whose other end every room it joins
        on its top storey reaches (the head) -- each straight onto that end
        or across the hall's own landing (`_reached`, the sensible check's
        `stair_climbable`) -- or a storey between whose rooms reach neither."""
        out = []
        for sh in self.p.shafts:
            if sh.block != b or kinds.get(sh.id) != "straight" or len(sh.levels) < 2 or sh.id not in state.flights:
                continue
            F = state.flights[sh.id]
            low, top = min(sh.levels), max(sh.levels)
            reach = {}
            for lv in sh.levels:
                L = state.storeys.get(lv)
                hid = f"{sh.id}@{lv}"
                H = L.rects.get(hid) if L is not None else None
                reach[lv] = [_reached(H, F, L.rects[j["to"]]) if H is not None else set()
                             for j in self.p.halls[hid]["joins"] if L is not None and j["to"] in L.rects]
            ends = tuple(_flight_ends(F))
            ok = any(all(foot in got for got in reach[low]) and
                     all(head in got for got in reach[top]) and
                     all(got for lv in sh.levels if low < lv < top for got in reach[lv])
                     for foot in ends for head in ends if head != foot)
            if not ok:
                out.append(sh.id)
        return out

    def _floor_needed(self, b, levels, kinds):
        """The cells of floor the largest of `levels` needs at the least:
        each room its target less KEEP_BAND, each stair hall its least hall
        -- the ground grown on the second pass is at least this large."""
        need = 0.0
        for lv in levels:
            n = 0.0
            for x in self.leaves_of(b, lv):
                if x in self.hall_ids:
                    fw, fd = STAIRS[kinds[x.rsplit("@", 1)[0]]]
                    bw, bd = Leaf._hall_base(fw, fd)
                    n += bw * bd
                else:
                    r = self.rooms[x]
                    n += (_stated_area(r) or room_target(r, stated=False)) * GROW_FLOOR_SHARE
            need = max(need, n)
        return int(need)

    @staticmethod
    def _severe(state, first):
        """Did a storey of this chain other than the first give way a shared
        wall (GROUND_ONLY) -- rooms its stair or its neighbour cannot reach?"""
        return any(c in GROUND_ONLY for lv, L in state.storeys.items() if lv != first for c in L.gave)

    def _carry(self, b, first, ups, downs, kinds, tower, combos, lookahead, margin, skip, min_area=0):
        """The first storey's `lookahead` cheapest outlines within `margin`
        of its cheapest -- of at least `min_area` cells, and but those in
        `skip`, carried before -- each carried with every other storey (the
        beam). Returns (the best chain or None, the cheapest first storey's
        cost, the outlines carried)."""
        each = max(2, lookahead // len(combos))
        carried = set(skip)
        got = self._grounds(b, first, kinds, combos, each, margin, min_area, frozenset(), [], lookahead, carried)
        if not got[1]:
            if min_area:
                return None, INF, set(skip)
            raise ValueError(f"block {b}: storey {first} could not be laid")
        cheapest, pool = got
        best = self._chains(b, first, ups, downs, kinds, tower, pool, False, None)
        # THE GROUND'S OUTLINE MAY STEP (`NOTCH_COST`): laid as one rectangle
        # wholly floor and carried, as before; then laid with notches and
        # carried after those -- each set drawn from within `margin` of its
        # own cheapest -- where storeys stand above or below it at most
        # NOTCH_LOOKAHEAD of them: those storeys' rooms stand over floor
        # only, in a rectangle of it, so a notch the ground alone prefers can
        # leave the storey above no rectangle to stand in (the shrine's
        # genkan porch, under the roost stair's hall: its upper floor gave
        # four asks way), and the whole chain decides.
        # ONLY WHERE A NOTCH HAS SOMETHING TO BUY, AND ROOM TO STAND: in the
        # slots of the rooms of the ground the best chain laid wholly floor
        # that want one (`_notch_wanted`), and only where they do not all
        # lie wholly under the storeys next to the ground (`_wholly_under`)
        # -- a notch there leaves an upper room over open ground, and the
        # notched pass found nothing in 7 of the shrine's 9 relays, the
        # unseen inn and its hospital, laying their grounds twice for it --
        # nor past NOTCH_WORK
        if first == 0 and not min_area and self.meter.by_storey.get((b, first), 0) <= NOTCH_WORK:
            wanted = self._notch_wanted(best.storeys[first] if best is not None else pool[0][1])
            if wanted and not (best is not None and (ups or downs) and self._wholly_under(best, first, wanted)):
                narrow = bool(ups or downs)
                limit = NOTCH_LOOKAHEAD if narrow else lookahead
                # ...each with notches on the outline of the ground the best
                # chain stands on too: the storeys above need the shape they
                # stood on (the shrine's first floor stands nine rows deep;
                # the grounds its notches made cheapest stood eight) -- and
                # laid for the ends of the flights that ground was laid for
                # alone: the shrine's s1, laid with notches for each of its
                # four ways round two flights, took 1.9 s to find no notch
                g = best.storeys[first] if best is not None else None
                sizes = [(g.outline.w, g.outline.d)] if narrow and g is not None else []
                if g is not None and g.ends:
                    combos = [dict(g.ends)]
                    each = max(2, lookahead // len(combos))
                # ...asking of it every ask the plain grounds were asked: a
                # notch never buys an ask given way (`_relaxed`, strict)
                self._strict = True
                try:
                    _least, notched = self._grounds(b, first, kinds, combos, each, margin, min_area, wanted, sizes,
                                                    limit, carried)
                finally:
                    self._strict = False
                best = self._chains(b, first, ups, downs, kinds, tower, notched, narrow, best)
        return best, cheapest, carried

    def _grounds(self, b, first, kinds, combos, each, margin, min_area, notch, sizes, limit, carried):
        """The first storey's outlines to carry, `(cheapest cost, [(cost,
        _Laid)])`: laid wholly floor, or with notches in the slots of the
        rooms `notch` names -- then those on the outlines of `sizes` first --
        at most `limit` (more by `sizes`) not yet in `carried`, which they
        join."""
        cands = []
        for combo in combos:
            cands += self.lay_free(b, first, self.leaves_of(b, first), kinds, each, combo, margin, min_area,
                                   notch=notch, outlines=sizes, plain_back=not notch)
        # THE FIRST STOREY'S TABLES ARE LET GO once its outlines are taken:
        # the storeys after it never read them, and they held the most memory
        # of any (the unseen merchant's ground, 1.2 M entries, kept while its
        # upper floor was laid); a second pass lays it again
        self._families = {k: v for k, v in self._families.items() if k[:2] != (b, first)}
        cands.sort(key=lambda t: t[0])
        if not cands:
            return INF, []
        least = cands[0][0]
        cands = [t for t in _distinct(cands, lambda t: t[1]) if t[0] <= least + margin]
        if sizes:
            # the notched grounds on the plain grounds' outlines, then the
            # notched grounds' own cheapest
            cands = sorted(cands, key=lambda t: ((t[1].outline.w, t[1].outline.d) not in sizes, t[0]))
            limit += len(sizes)
        cands = [t for t in cands if _laid_key(t[1]) not in carried and (t[1].pads or not sizes)][:limit]
        carried |= {_laid_key(t[1]) for t in cands}
        return least, cands

    def _chains(self, b, first, ups, downs, kinds, tower, cands, narrow, best):
        """The best chain of `best` and each ground of `cands` [(cost,
        _Laid)] carried with every other storey of the block -- cheapest
        first, a chain dropped once dearer than the best found. `narrow`: the
        grounds have notches, and are carried one state a storey."""
        # each ground outline carries its own beam: a deeper ground that
        # costs more for itself but holds the storeys above is not pruned
        # before the storey that needs it is laid (the owner's shrine: a
        # 15 x 10 ground carried a roof room the 14 x 9 one could not)
        for c0, laid0 in sorted(cands, key=lambda t: t[0]):
            st = _State(laid0.cost + laid0.penalty, {first: laid0}, {}, {})
            # A NOTCH NEVER LEAVES A LANDING NOBODY REACHES: a ground with
            # notches, or a storey laid on one, that seals landing cells
            # (`_settle`) is not carried -- the plain grounds are. The shrine
            # skeleton's notched ground (genkan 3 x 2 beside a porch) ran its
            # stair halls the whole north row, and the up flight, kept along
            # the hall's wall, sealed the two cells past its head; laid wholly
            # floor it sealed none (test_a_landing_lies_where_its_storey_reaches_it)
            if self._settle(b, kinds, first, laid0, st) and narrow:
                continue
            states = [st]
            # a ground with notches carries the storeys beside it only as the
            # plan asks them: one that would give an ask way to stand on it
            # is not laid (`_relaxed`), the plain grounds hold it better --
            # its give-way tries were most of what the notched grounds cost
            self._strict = narrow
            try:
                for lv in ups + downs:
                    nxt = []
                    for st in states:
                        for laid in self._lay_next(b, lv, first, st, kinds, tower):
                            st2 = _State(st.total + self._weigh(lv, laid), dict(st.storeys), dict(st.flights),
                                         dict(st.reach))
                            st2.storeys[lv] = laid
                            if self._settle(b, kinds, lv, laid, st2) and narrow:
                                continue
                            nxt.append(st2)
                    nxt.sort(key=lambda t: t.total)
                    states = nxt[:1 if self.large or narrow else BEAM]
                    if not states or (best is not None and states[0].total >= best.total):
                        states = []
                        break
            finally:
                self._strict = False
            if states and (best is None or states[0].total < best.total - 1e-9):
                best = states[0]
        return best

    def _end_combos(self, b, lv, kinds, fixed):
        """[{hall: end}]: every way round the straight flights first laid on
        storey `lv` (not in `fixed`) can be reached there, at most END_SHAFTS
        of them -- a flight to a storey of several rooms first."""
        free = []
        # ON A LARGE BUILDING TOO (the fix round's phase 2): carried one way
        # round only, the unseen hospital's main stair was placed for its
        # ground alone, and its upper corridor reached the same end
        for sh in self.p.shafts:
            if sh.block != b or lv not in sh.levels or sh.id in fixed or kinds[sh.id] != "straight" \
                    or len(sh.levels) < 2:
                continue
            run = self._hall_leaf(f"{sh.id}@{lv}", kinds[sh.id], None).run
            if run is None:
                continue
            others = max(sum(1 for x in self.leaves_of(b, v) if x not in self.hall_ids)
                         for v in sh.levels if v != lv)
            free.append((-others, sh.id, (8, 2) if run == "ew" else (1, 4)))
        combos = [{}]
        for _o, sid, pair in sorted(free)[:END_SHAFTS]:
            combos = [dict(c, **{f"{sid}@{lv}": e}) for c in combos for e in pair]
        return combos

    def _weigh(self, lv, laid):
        """What a storey after the first adds to its chain's total. NO STOREY
        ABOVE OR BELOW SIZES THE GROUND (the owner's rulings: of 2026-10-10,
        chat 164, the roof room's huge nest grew the whole building; and of
        2026-10-15, never inflate a ground room to carry the storey above):
        its own cost -- its rooms' sizes, their fit, its roof -- counts at
        FITTED_WEIGHT, so it squeezes into the floor the ground made for
        itself rather than growing it (the lab's run 2: a full first storey
        a third dearer on the 15 x 9 ground chose a 15 x 10 one and its main
        hall half again its stated size). What it gave way -- an ask, floor
        under it, the footprint -- counts in full."""
        return FITTED_WEIGHT * (laid.cost - laid.ledge) + laid.penalty

    def _settle(self, b, kinds, lv, laid, st):
        """Fix the flights of the shafts this storey is the first to lay. A
        landing it leaves where no body on it reaches without crossing the
        flight (`_sealed`) costs the chain DEAD_LANDING_COST a cell, so the
        beam keeps the layouts without one -- save a landing a window above
        asks (`_window_landing`): that floor is for the roof beside the room
        above, sealed by design (the review's visual 3; the owner's call).
        Returns the landing cells it charged."""
        sealed = 0
        for sh in self.p.shafts:
            if sh.block != b or lv not in sh.levels or sh.id in st.flights:
                continue
            F, reach, dead = self._fix_flight(sh, kinds[sh.id], lv, laid)
            st.flights[sh.id] = F
            st.reach[sh.id] = (lv, reach)
            if dead and not self._window_landing(f"{sh.id}@{lv}", lv):
                st.total += DEAD_LANDING_COST * dead
                sealed += dead
        return sealed

    def _lay_next(self, b, lv, first, st, kinds, tower):
        """Storey `lv` laid on the carried state `st`: above the first storey
        on the floor of the one below, below it under the one above. Its
        cheapest BEAM_EACH layouts."""
        below = lv < first
        # the storey it stands on (or under): the nearest laid toward the
        # first -- a block's storeys may skip one (the code review's finding
        # 12: a belfry at storey 2 over nothing at 1 raised KeyError)
        near = min(v for v in st.storeys if v > lv) if below else max(v for v in st.storeys if v < lv)
        base = st.storeys[near]
        ids = self.leaves_of(b, lv)
        pins, hall_end = {}, {}
        for sh in self.p.shafts:
            if sh.block == b and lv in sh.levels and sh.id in st.flights:
                hid = f"{sh.id}@{lv}"
                pins[hid] = st.flights[sh.id]
                lv0, reach = st.reach[sh.id]
                need = self._ends_needed(sh, lv, reach, lv0)
                if need:
                    hall_end[hid] = need
        floor = set()
        for r in base.rects.values():
            floor |= r.cells()
        # A NOTCH OF THE GROUND MAY STAND UNDER THE EAVES OF THE STOREY ABOVE
        # (the fix round's phase 3): that storey's outline may reach over it,
        # roof there -- a porch under the main roof -- but none of its rooms
        # (`_lay_one` drops a layout standing a room over one). Below the
        # ground a storey lies under rooms only
        roofed = set() if below or base.level != 0 else {c for r in base.pads for c in r.cells()}
        # above the ground each pinned hall may keep the landing its hall on
        # the storey below took beside the run (KEPT_LANDING_COST)
        keeps = {} if below else {hid: base.rects.get(f"{hid.rsplit('@', 1)[0]}@{near}") for hid in pins}
        # ...and each room a pinned stair is the only way into stands over
        # the rooms it climbs from below where it can (OVER_COST)
        over = {}
        if not below and lv > 0:
            for hid in sorted(pins):
                down = f"{hid.rsplit('@', 1)[0]}@{near}"
                # not over a corridor: two paces wide, no room stands over it
                # (the shrine's roost, its stair up from the hallway)
                under = [base.rects[j["to"]] for j in self.p.halls.get(down, {}).get("joins") or ()
                         if j["to"] in base.rects and j["to"] in self.rooms
                         and purpose_key(self.rooms[j["to"]]) not in CORRIDORS]
                if not under:
                    continue
                for j in self.p.halls[hid]["joins"]:
                    if j["to"] in ids and not any(o in ids and o not in self.hall_ids
                                                  for o in _joins(j["to"], self.rooms)):
                        over.setdefault(j["to"], [])
                        over[j["to"]] += [r for r in under if r not in over[j["to"]]]
        # a storey of one room rising sheer over its stair (`_sheer_box`)
        sheer = None if below or tower or lv in self.smaller else self._sheer_box(b, lv, ids, base, pins)
        combos = self._end_combos(b, lv, kinds, set(st.flights))
        out = []
        for combo in combos:
            out += self._lay_one(b, lv, ids, kinds, pins, dict(hall_end, **combo), floor, base, below, tower, near,
                                 keeps, over, sheer, roofed)
        for laid in out:
            laid.penalty += self._support_hint(b, lv, laid, st.flights)
        out.sort(key=lambda L: L.cost + L.penalty)
        return _distinct(out, lambda L: L)[:(1 if self.large else BEAM_EACH) * len(combos)]

    def _support_hint(self, b, lv, laid, fixed):
        """What a storey costs the storey above it before that one is laid:
        a flight this storey lays first climbs to a room that stands on the
        side of its hall its own wall asks (the roof room north of its
        stair) and must stand over floor; each cell of the strip
        SUPPORT_DEPTH deep along that side of the hall that is not floor
        here costs SUPPORT_HINT, so the beam keeps the layouts the storey
        above can stand on."""
        floor = set()
        for r in laid.rects.values():
            floor |= r.cells()
        short = 0
        for sh in self.p.shafts:
            if sh.block != b or lv not in sh.levels or sh.id in fixed:
                continue
            up = [v for v in sh.levels if v > lv] if lv >= 0 else [v for v in sh.levels if v < lv]
            if not up or (lv >= 0 and up[0] <= 0):
                continue
            nxt = up[0]
            hall = laid.rects.get(f"{sh.id}@{lv}")
            if hall is None:
                continue
            for st in sh.flights:
                for rid in (st.low, st.high):
                    if self.rooms[rid]["level"] != nxt or not st.at.get(rid):
                        continue
                    side = _OPP[st.at[rid]]          # the room above stands on this side of the hall
                    dx, dy = _STEP[side]
                    edge = [c for c in hall.cells()
                            if (c[0] + dx, c[1] + dy) not in hall.cells()]
                    for c in edge:
                        for k in range(1, SUPPORT_DEPTH + 1):
                            if (c[0] + dx * k, c[1] + dy * k) not in floor:
                                short += 1
        return SUPPORT_HINT * short

    def _lay_one(self, b, lv, ids, kinds, pins, hall_end, floor, base, below, tower, near=None, keeps=None,
                 over=None, sheer=None, roofed=frozenset()):
        """One storey's cheapest BEAM_EACH layouts for one choice of the
        ends its own flights take, with the fallbacks the owner's rules
        allow and price. `roofed`: notch cells of the ground below its
        outline may reach over, its rooms never."""
        if roofed:
            got = self._lay_one(b, lv, ids, kinds, pins, hall_end, floor | roofed, base, below, tower, near, keeps,
                                over, sheer)
            got = [L for L in got if not any(r.cells() & roofed for r in L.rects.values())]
            # where every way it was laid stood a room over the notch, it is
            # laid on the floor alone, as before
            return got or self._lay_one(b, lv, ids, kinds, pins, hall_end, floor, base, below, tower, near, keeps,
                                        over, sheer)
        if below:
            # UNDER THE HOUSE (the owner's rule): the storey stands inside the
            # floor of the storey above -- or, under a storey dug itself,
            # inside its outline, earth and all -- under the rooms its stairs
            # join there where it can (`UNDER_COST`). IT IS DUG, NOT BUILT
            # (`EARTH_COST`): what of its rectangle no room takes is earth
            near = lv + 1 if near is None else near
            under = set()
            for sh in self.p.shafts:
                if sh.block != b or lv not in sh.levels or near not in sh.levels:
                    continue
                for j in self.p.halls.get(f"{sh.id}@{near}", {}).get("joins") or ():
                    r = base.rects.get(j["to"])
                    if r is not None:
                        under |= r.cells()
            allowed = base.outline.cells() if near < 0 else floor
            out = self.lay_region(b, lv, ids, kinds, pins, hall_end, allowed, base.outline, EARTH_COST,
                                  count=BEAM_EACH, under=under or None, earth=True)
            if not out:
                # never measured: with every ask that may give way given the
                # storey still found no rectangle under the house -- it
                # reaches past the footprint, priced by the cell
                o = base.outline
                box = Rect(o.x - BELOW_REACH, o.y - BELOW_REACH, o.w + 2 * BELOW_REACH, o.d + 2 * BELOW_REACH)
                out = self.lay_region(b, lv, ids, kinds, pins, hall_end, box.cells(), box, EARTH_COST, beyond=o,
                                      count=BEAM_EACH, earth=True)
                for laid in out:
                    laid.penalty += BEYOND_FLAT
                    laid.warnings.append(f"storey {lv} could not lie under the house as its stairs and joins "
                                         f"ask; it reaches beyond the house's walls")
            return out
        pad = PAD_ROOF if lv in self.smaller else PAD_UPPER
        out = []
        if tower:
            out = self.lay_region(b, lv, ids, kinds, pins, hall_end, floor, base.outline, None,
                                  exact_box=base.outline, count=BEAM_EACH, keeps=keeps, over=over)
        elif sheer is not None:
            out = self.lay_region(b, lv, ids, kinds, pins, hall_end, floor, base.outline, None,
                                  exact_box=sheer, count=BEAM_EACH, keeps=keeps, over=over, whole=True)
        if not out:
            out = self.lay_region(b, lv, ids, kinds, pins, hall_end, floor, base.outline, pad, count=BEAM_EACH,
                                  keeps=keeps, over=over, whole=sheer is not None)
        if not out:
            # past every ask that may give way: the storey stands within the
            # outline below, over roof where it must -- priced by the cell
            # so a carried state that keeps every room over a room wins
            out = self.lay_region(b, lv, ids, kinds, pins, hall_end, base.outline.cells(), base.outline, pad,
                                  count=BEAM_EACH, keeps=keeps, over=over, whole=sheer is not None)
            for laid in out:
                bare = sum(len(r.cells() - floor) for r in laid.rects.values())
                laid.penalty += UNSUPPORTED_COST * bare
                if bare:
                    # said only where a cell of it does stand over no floor
                    # (the code review's finding 11: said of a tower storey
                    # every room of which stood over a room)
                    laid.warnings.append(f"storey {lv} could not stand wholly over the floor below")
        return out

    def _sheer_box(self, b, lv, ids, base, pins):
        """A STOREY OF ONE ROOM RISES SHEER over the room its stair climbs
        from and that stair's hall, where those two make a rectangle: over a
        storey of one room, as a tower's storeys do (`lay_block`'s `tower`);
        over a room among others, where it fills that column at about its
        own size -- its target at least 1 - KEEP_BAND of the box less the
        halls. The box it is laid in first, wholly floor, its stair's
        landing below kept whole -- else None. (The unseen watchtower: a
        guardroom beside its foot made the block no tower, and each storey
        above stepped out over the guardroom, a pace of roof beside its
        stair for a window on the stair's wall. A loft of 3 m2 over a hall
        of 17 among a house's rooms is no tower storey: made to rise sheer
        it came out three times its size, the code review's byres.) Not
        under the roof: a storey marked smaller stands where its floor
        allows."""
        rooms = [x for x in ids if x not in self.hall_ids]
        if len(rooms) != 1 or lv <= 0:
            return None
        cells, halls = set(), 0
        for hid in sorted(pins):
            below = f"{hid.rsplit('@', 1)[0]}@{base.level}"
            hall = base.rects.get(below)
            if hall is None:
                continue
            cells |= hall.cells()
            halls += hall.w * hall.d
            for j in self.p.halls.get(below, {}).get("joins") or ():
                r = base.rects.get(j["to"])
                if r is not None:
                    cells |= r.cells()
        if not cells:
            return None
        x0, y0 = min(c[0] for c in cells), min(c[1] for c in cells)
        x1, y1 = max(c[0] for c in cells) + 1, max(c[1] for c in cells) + 1
        if (x1 - x0) * (y1 - y0) != len(cells):
            return None
        alone = sum(1 for k in base.rects if k not in self.hall_ids) == 1
        if not alone and self._room_leaf(rooms[0], lv).target < (1.0 - KEEP_BAND) * (len(cells) - halls):
            return None
        return Rect(x0, y0, x1 - x0, y1 - y0)

    # -- where the blocks stand ------------------------------------------------

    def place_blocks(self, laid):
        """Each block's offset: the entrance's block at the origin, each
        other beside, apart from or toward the block it names, as
        `_place_blocks` stands them -- the block's own outlines laid by this
        core. A block standing only below the ground stands beside the
        anchor's storey at its level, and a block a room of the anchor joins
        stands centred on that room, so the two share a wall."""
        base = {}
        for b, storeys in laid.items():
            if 0 in storeys:
                base[b] = storeys[0].outline
            else:
                lv = min(storeys, key=lambda v: (abs(v), v))
                base[b] = storeys[lv].outline
        first = self.home
        placed = {first: Rect(0, 0, base[first].w, base[first].d)}
        offset = {first: (-base[first].x, -base[first].y)}
        # IN PLAN ORDER (the fix round's phase 3): a block that must slide
        # off another one placed before it (`_slide`) slides, and the plan's
        # first keeps its place -- in the order the plan lists its blocks
        rank = {bid: k for k, bid in enumerate(self.declared)}
        pending = sorted((b for b in laid if b != first), key=lambda b: (rank.get(b, len(rank)), b))
        walls = {}                      # blocks placed against a joined room (`_slide`)
        for _round in range(len(pending) + 1):
            for b in list(pending):
                decl = self.declared.get(b, {})
                beside = decl.get("beside") or {}
                anchor = beside.get("block") if beside.get("block") in placed else first
                side = str(beside.get("side") or "")[:1]
                if not beside:
                    for pb, pdecl in sorted(self.declared.items()):
                        pbes = pdecl.get("beside") or {}
                        if pb in placed and pbes.get("block") == b and str(pbes.get("side") or "")[:1] in _SIDES:
                            anchor, side = pb, _OPP[str(pbes["side"])[:1]]
                            decl = dict(decl, apart=pdecl.get("apart"))
                            break
                # a cavern stands on the side its basement storey left it
                # (`_cave_side`)
                got = self.side_override.get(b)
                if got is not None and got[0] in placed:
                    anchor, side = got
                if anchor not in placed:
                    continue
                w, d = base[b].w, base[b].d
                gap = 3 if decl.get("apart") else 0
                if side not in _SIDES:
                    side = {"n": "e", "s": "e", "e": "n", "w": "n"}[self.front]
                a = placed[anchor]
                mine = sorted(laid[b])
                ax, ay = offset[anchor]
                # A BLOCK WITH NO STOREY ON THE GROUND -- a cavern below it,
                # an oriel above it -- stands beside the anchor's storey at
                # its own level nearest the ground: an oriel beside the
                # ground's outline stood off a first floor set back from it,
                # its room's wall shared with none (the code review's e20b)
                if 0 not in mine and any(lv in laid[anchor] for lv in mine):
                    lv = min((v for v in mine if v in laid[anchor]), key=lambda v: (abs(v), v))
                    o = laid[anchor][lv].outline
                    a = Rect(o.x + ax, o.y + ay, o.w, o.d)
                if side == "n":
                    r = Rect(a.x + (a.w - w) // 2, a.y - d - gap, w, d)
                elif side == "s":
                    r = Rect(a.x + (a.w - w) // 2, a.y + a.d + gap, w, d)
                elif side == "e":
                    r = Rect(a.x + a.w + gap, a.y + (a.d - d) // 2, w, d)
                else:
                    r = Rect(a.x - w - gap, a.y + (a.d - d) // 2, w, d)
                # A BLOCK A ROOM OF THE ANCHOR JOINS STANDS WITH ITS OWN JOINED
                # ROOM CENTRED ON THAT ROOM, so the two share a wall (the code
                # review's finding 5: the whole block was centred on the
                # anchor's room, and a porch standing south of a row of four
                # stood under the parlour, its hall's wall shared with none;
                # a byre range's dairy, off the kitchen, under the hall)
                joined = self._joined_rooms(anchor, b, laid)
                if joined is not None and not decl.get("apart"):
                    jr, br = joined
                    jr = Rect(jr.x + ax, jr.y + ay, jr.w, jr.d)
                    if side in "ns":
                        r = Rect(jr.x + (jr.w - br.w) // 2 - br.x + base[b].x, r.y, w, d)
                    else:
                        r = Rect(r.x, jr.y + (jr.d - br.d) // 2 - br.y + base[b].y, w, d)
                    r = self._slide(b, r, side, jr, br, base[b], laid, placed, offset, walls)
                toward = str(decl.get("toward") or "")[:1]
                if toward in _SIDES and toward not in (side, _OPP[side]):
                    if toward == "w":
                        r = Rect(a.x - w, r.y, w, d)
                    elif toward == "e":
                        r = Rect(a.x + a.w, r.y, w, d)
                    elif toward == "n":
                        r = Rect(r.x, a.y - d, w, d)
                    else:
                        r = Rect(r.x, a.y + a.d, w, d)
                if decl.get("apart"):
                    way = toward if toward in _SIDES and toward not in (side, _OPP[side]) \
                        else {"n": "e", "s": "e", "e": "s", "w": "s"}[side]
                    sx, sy = _STEP[way]

                    def crowds(q, r):
                        if r.cells() & q.cells():
                            return True
                        gx = max(q.x - (r.x + r.w), r.x - (q.x + q.w))
                        gy = max(q.y - (r.y + r.d), r.y - (q.y + q.d))
                        return (gx == 1 and gy < 0) or (gy == 1 and gx < 0)

                    standing = [q for pb, q in placed.items() if any(lv >= 0 for lv in laid[pb])]
                    for _step in range(len(placed) + 1):
                        if not any(crowds(q, r) for q in standing):
                            break
                        r = Rect(r.x + sx * (w + BLOCK_GAP), r.y + sy * (d + BLOCK_GAP), w, d)
                placed[b] = r
                offset[b] = (r.x - base[b].x, r.y - base[b].y)
                pending.remove(b)
        for b in pending:                       # a block nothing places: beside the first, east
            a = placed[first]
            r = Rect(a.x + a.w + 3, a.y, base[b].w, base[b].d)
            placed[b] = r
            offset[b] = (r.x - base[b].x, r.y - base[b].y)
        return offset

    def _joined_rooms(self, anchor, b, laid):
        """(the room of `anchor` a room of `b` joins on a storey both hold,
        in anchor block coordinates; that room of `b`, in its own), or
        None."""
        for rid, r in sorted(self.rooms.items()):
            if r["block"] != b or r["level"] not in laid[b]:
                continue
            for other in sorted(_joins(rid, self.rooms)):
                o = self.rooms[other]
                if o["block"] == anchor and o["level"] == r["level"] and o["level"] in laid[anchor]:
                    ar = laid[anchor][o["level"]].rects.get(other)
                    br = laid[b][r["level"]].rects.get(rid)
                    if ar is not None and br is not None:
                        return ar, br
        return None

    def _slide(self, b, r, side, jr, br, bo, laid, placed, offset, walls):
        """BLOCKS OFF ONE WALL STAND APART ALONG IT (the code review's finding
        4: two caverns off one basement wall laid on the same nine cells).
        Block `b`, placed at `r` with its joined room `br` centred on the
        anchor's `jr`, that stands on the same ground as a block placed
        before it on a storey both hold takes the FIRST FREE STRETCH of the
        wall instead -- from the wall's west or north end, the first place
        where it overlaps none and its room still shares MIN_SHARED paces
        of wall with the anchor's -- and where none is free and the block it
        meets stands against the same wall, that block takes the wall's
        first stretch and `b` the next: the plan's order along the wall
        (`place_blocks` reads the blocks in plan order). Where nothing frees
        a stretch, `b` stays where it was put, and the bridge refuses the
        building (`layout_bridge._standing_breaches`). `walls` {block:
        (side, jr, br, base outline)} of the blocks placed so; `b` is
        entered there."""
        walls[b] = (side, jr, br, bo)

        def outlines(q, rect, base):
            return {lv: Rect(L.outline.x + rect.x - base.x, L.outline.y + rect.y - base.y, L.outline.w,
                             L.outline.d) for lv, L in laid[q].items()}

        def clash(q, rect, base, skip=()):
            mine = outlines(q, rect, base)
            for o, orect in placed.items():
                if o == q or o in skip:
                    continue
                ox, oy = offset[o]
                for lv, L in laid[o].items():
                    if lv in mine and Rect(L.outline.x + ox, L.outline.y + oy, L.outline.w,
                                           L.outline.d).overlaps(mine[lv]):
                        return o
            return None

        def stretch(q, rect, sd, jr_, br_, base, skip=()):
            along = sd in "ns"
            lo, hi = (jr_.x, jr_.x + jr_.w) if along else (jr_.y, jr_.y + jr_.d)
            own = br_.x - base.x if along else br_.y - base.y
            size = br_.w if along else br_.d
            need = min(MIN_SHARED, size, hi - lo)
            for room0 in range(lo - size + need, hi - need + 1):
                pos = room0 - own
                cand = Rect(pos, rect.y, rect.w, rect.d) if along else Rect(rect.x, pos, rect.w, rect.d)
                if clash(q, cand, base, skip) is None:
                    return cand
            return None

        hit = clash(b, r, bo)
        if hit is None:
            return r
        got = stretch(b, r, side, jr, br, bo)
        if got is not None:
            return got
        w = walls.get(hit)
        if w is not None and w[0] == side and hit in placed:
            _s, jq, bq, oq = w
            moved = stretch(hit, placed[hit], side, jq, bq, oq, skip=(b,))
            if moved is not None:
                keep = placed[hit], offset[hit]
                placed[hit] = moved
                offset[hit] = (moved.x - oq.x, moved.y - oq.y)
                got = stretch(b, r, side, jr, br, bo)
                if got is not None:
                    return got
                placed[hit], offset[hit] = keep
        return r

    # -- the whole ---------------------------------------------------------------

    def _cave_side(self, cb, laid):
        """Where a block standing only below the ground (a cavern) stands:
        beside the laid block one of its rooms opens into, beyond the wall of
        that room the plan asks -- or, where a stair or a room of that
        storey keeps that wall (the storey lies under the house, so nothing
        moves it), beyond another wall of the room its storey leaves
        exposed: a side beside the asked one first -- one the room's own
        things are not asked against, then the one nearer the house's edge
        (the cavern reaches out from under the house soonest) -- then the
        side opposite. A warning names what kept the wall. Sets
        `side_override[cb]`."""
        for rid in sorted(r for r, x in self.rooms.items() if x["block"] == cb):
            lv = self.rooms[rid]["level"]
            for other, (side, _o, _k) in sorted(_joins(rid, self.rooms).items()):
                ab = self.rooms[other]["block"]
                if ab == cb or ab not in laid or self.rooms[other]["level"] != lv or lv not in laid[ab]:
                    continue
                L = laid[ab][lv]
                room = L.rects.get(other)
                if room is None:
                    continue
                asked = self._block_side(ab, cb, _OPP[side] if side in _SIDES else None)
                o = L.outline
                edge = {"n": room.y == o.y, "s": room.y + room.d == o.y + o.d,
                        "w": room.x == o.x, "e": room.x + room.w == o.x + o.w}
                exposed = [sd for sd in _SIDES if edge[sd]]
                if asked not in _SIDES or asked in exposed or not exposed:
                    self.side_override[cb] = (ab, asked if asked in _SIDES else (exposed or ["n"])[0])
                    return
                house = laid[ab].get(self._first(ab), L).outline
                reach = {"n": room.y - house.y, "s": house.y + house.d - room.y - room.d,
                         "w": room.x - house.x, "e": house.x + house.w - room.x - room.w}
                # a wall the room's own things are asked against keeps them:
                # the cavern opens off another where it can (the shrine's
                # basement asks its workbench on its east wall: the cavern
                # turned east took it on 6 of 14 relays). Read from the plan
                # as written -- `_read` spreads a thing asked "walls" over
                # all four, which says nothing about any one
                held = set()
                for r in self.p.spec.get("rooms") or ():
                    if isinstance(r, dict) and r.get("id") == other:
                        held = {str(fx.get("at") or "").casefold() for fx in r.get("fixtures") or ()
                                if isinstance(fx, dict)} & set(_SIDES)
                ring = list(_SIDES)
                k = ring.index(asked)
                beside = [ring[(k + 1) % 4], ring[(k + 3) % 4]]
                pref = sorted((sd for sd in beside if sd in exposed),
                              key=lambda sd: (sd in held, reach[sd], beside.index(sd)))
                pref += [sd for sd in (_OPP[asked],) if sd in exposed]
                chosen = pref[0]
                # what keeps the asked wall: the leaves across it
                keep = []
                for kid, r in sorted(L.rects.items()):
                    if kid == other:
                        continue
                    if asked == "n" and r.y + r.d == room.y or asked == "s" and r.y == room.y + room.d:
                        touch = min(r.x + r.w, room.x + room.w) - max(r.x, room.x) > 0
                    elif asked == "w" and r.x + r.w == room.x or asked == "e" and r.x == room.x + room.w:
                        touch = min(r.y + r.d, room.y + room.d) - max(r.y, room.y) > 0
                    else:
                        touch = False
                    if touch:
                        if kid in self.hall_ids:
                            sid = kid.rsplit("@", 1)[0]
                            keep.append(self.shafts[sid].name or sid)
                        else:
                            keep.append(self.layout.names.get(kid, kid))
                name = self.layout.names
                kept_by = " and ".join(keep) if keep else "the storey's own floor"
                self.warnings.append(f"{name.get(rid, rid)} was asked beyond {name.get(other, other)}'s {asked} "
                                     f"wall, which keeps {kept_by} under the house; it stands beyond its {chosen} wall")
                self.side_override[cb] = (ab, chosen)
                return

    def division(self):
        laid, flights = {}, {}
        order = [self.home] + sorted(b for b in self.levels if b != self.home)
        # a block standing only below the ground is laid after the blocks it
        # may open from: the side it stands on is the one their storeys leave
        # exposed (`_cave_side`)
        order = [b for b in order if b == self.home or b not in self.below_only] + \
            [b for b in order if b != self.home and b in self.below_only]
        for b in order:
            if b != self.home and b in self.below_only:
                self._cave_side(b, laid)
            storeys, fl = self.lay_block(b)
            laid[b] = storeys
            flights.update(fl)
        offset = self.place_blocks(laid)
        # each storey problem reads its relations afresh, and a sentence about
        # them is written once
        chosen, outlines, hall_at, warnings = {}, {}, {}, list(dict.fromkeys(self.warnings))
        for b in order:
            dx, dy = offset[b]
            outlines[b] = {}
            for lv in sorted(laid[b]):
                L = laid[b][lv]
                o = L.outline
                outlines[b][lv] = Rect(o.x + dx, o.y + dy, o.w, o.d)
                parts = {}
                for rid in sorted(L.rects):
                    r = L.rects[rid]
                    parts[rid] = Rect(r.x + dx, r.y + dy, r.w, r.d)
                for r in sorted(L.pads, key=lambda q: (q.y, q.x)):
                    q = Rect(r.x + dx, r.y + dy, r.w, r.d)
                    # below the ground, what no room takes is earth (`EARTH_
                    # COST`); on it, open ground -- a notch in the outline
                    # (`NOTCH_COST`); above it, roof or void (`_materialize`)
                    kind = "earth" if lv < 0 else "notch" if lv == 0 else "spare"
                    parts[f"{kind}:{lv}:{q.x}:{q.y}"] = q
                chosen[(b, lv)] = parts
                for w in L.warnings:
                    if w not in warnings:
                        warnings.append(w)
        for sid in sorted(flights):
            kind, F = flights[sid]
            b = self.shafts[sid].block
            dx, dy = offset[b]
            hall_at[sid] = (kind, Rect(F.x + dx, F.y + dy, F.w, F.d))
        return Division(chosen=chosen, hall_at=hall_at, outlines=outlines, warnings=warnings)


def arrange(p) -> Division:
    """The tier's core: the building `p` (`layout_solver._prepare(...,
    own_outlines=True)`) arranged from its relations and sized, one
    deterministic solve."""
    return _Building(p).division()


#: THE LAST DIVISION LAID, kept to finish the same spec once more with its
#: doors in the lab's order (`solve_arranged(face=False)`, the bridge's
#: `_unturned`): the core is deterministic, so that never arranges the
#: building twice -- the merchant's core alone is 72 s. One entry, `(spec as
#: JSON, Division)`, replaced by every solve that arranges; read by no other.
_LAST_DIVISION = [None]


def solve_arranged(spec, seed=SEED, face=True):
    """`layout_solver.solve` with this core in place of the lab's search: one
    solve, the same for every seed (the seed is read by nothing here).
    `face`: `layout_solver._finish`'s; off, a spec just arranged is finished
    again from its division (`_LAST_DIVISION`), not arranged again."""
    try:
        key = json.dumps(spec, sort_keys=True, default=str)
    except (TypeError, ValueError):
        key = None                      # a spec JSON cannot spell is never kept
    last = _LAST_DIVISION[0]
    if not face and key is not None and last is not None and last[0] == key:
        kept = copy.deepcopy(last[1])

        def core(p):
            return kept
    else:
        def core(p):
            div = arrange(p)
            _LAST_DIVISION[0] = (key, copy.deepcopy(div)) if key is not None else None
            return div
    return solve_with(spec, core, seed, own_outlines=True, face=face)
