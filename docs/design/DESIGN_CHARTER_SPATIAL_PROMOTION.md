# Design: what a promoted charter body knows about where it is

**Status: UNBUILT on main; PROTOTYPED on a branch (2026-09-02).** This is a
problem statement and an options list, not a plan. On main nothing attempts
the transfer described here; `charter_runtime.registry_warnings` now says per
place when a charter place is not a room in the frame. The worktree branch
carrying `tests/test_charter_traversal.py` prototypes the route half -- bodies
walk the shared graph one room at a time and record the edges, and a
promoted body inherits the town's public rooms plus its own walked routes as
`place_graph` -- under option A (one namespace by construction). The
measurements and the arguments against merging it as it stands are in
`docs/UNBUILT.md` §1.10a.

A charter body promoted to a major character arrives knowing nothing about a
building it has worked in for months. The promotion path mints a sheet, seeds
mutual recognition and starts writing psychology
(`persist/commit_background.py::promote_background_character`), and it carries
across no spatial knowledge at all — because there is currently no
correspondence along which such knowledge could travel.

This document states what each side holds, why the gap is two gaps rather than
one, and what the options cost. It deliberately stops short of choosing.

## The question

A charter body — say `canteen_supply_duty:0001`, "Tilda Cimmerian", competence
`logistics: 2`, berthed at `staff_canteen` — is promoted. She becomes a major
character with a place graph, a memory and a psychology. What should she know
about the facility, and where does that knowledge come from?

The intuitive answer is "everything she has walked". The engine cannot supply
it, for two independent reasons.

## What each side holds

**A major character navigates a place graph.** `chat_chars.state.place_graph`,
written only by `record_spatial_experience`, with nodes keyed by **room id**
and edges laid down by walking. `world/place_purpose.py`'s module docstring
states the constraint that matters here:

> a node needs a rid, hearsay carries none, and nothing can route to a room
> with no rid anyway

So the graph's vocabulary is scene room ids, and its edges are a record of
having moved.

**A charter body navigates places and posts.** A body row carries `place`,
`berth` and `home_post` (`world/charter_runtime.py`, registry state). Its
movement record is `stood`, and `stood` is a tally:

    "canteen_supply_duty:0001": {"canteen_supply_duty": 34}

That is thirty-four occasions of standing at a post. It is not a path, and it
names a post rather than a room.

## The gap is two gaps

**1. The namespaces are disjoint.** Measured on chat 84, the only chat where
the charter system has run for more than one turn (14 turns, 37 bodies, 36
minds, 42 practices):

| | |
|---|---|
| scene rooms | `observation_room`, `interview_cell`, `elevator_hall`, `hallway_floor1` |
| charter places | `ethics_office`, `personnel_office`, `psych_office`, `research_lab`, `scp073_area`, `scp105_area`, `scp343_area`, `scp999_area`, `staff_canteen` |
| shared ids | **none** |

Nothing establishes a correspondence and nothing checks for one. The two
systems were built to different vocabularies and have never been introduced.

**2. Even with a mapping, there are no edges to transfer.** `stood` counts
occasions at a post. A place graph is nodes *and routes*. So a perfect
place-to-rid mapping would yield a set of nodes with no adjacency — a
character who knows the canteen exists and cannot get there from anywhere.

That failure mode is already measured. `agents/character.py:1911` records a
character whose place graph held "a complete, optimal 28-room route" and the
surrounding work (`docs/experiments/MAZE_ARMS.md`) exists because NPCs were
observed backtracking, which is the signature of navigating without a usable
graph. A promoted body with nodes and no edges is that failure by
construction, and it would look like a model problem.

## A third thing this touches, recorded because it was found in the same look

`agents/background.py:320-333` asks which charter bodies are near by passing
the player's **room id** and its ambient scope to
`charter_runtime.background_presence_records(cid, places=...)`, which filters
bodies by **place**. With the namespaces disjoint the intersection is always
empty, so `charter_near` is always `False` — silently, and inside a bare
`except Exception` that would swallow a raise as readily as a miss.

This is not the promotion problem, but it has the same cause, and it means the
37 bodies in chat 84 have never been in a room with anyone. It is the reason
the charter system reads as unexercised: not that nobody played it, but that
the scene never contained a place its people live in.

## Correction, measured after the first draft

The draft above assumed charter places and scene rooms are two namespaces that
ought to correspond. They are not, and the code says so.

`world/charter_run.py:420` — **"A scene is optional. Without one the institution
is a single place and everyone can stand any post, which is the right
simplification for six people in one hull and the wrong one for five hundred
across ninety compartments."** The institution carries its OWN optional
geography at `charter["scene"]`, distinct from the chat's scene blob.

Measured across all four charter worlds in the corpus (chats 84, 83, 93, 94):
**none of them has a charter scene.** So every one is a flat institution whose
"places" are labels rather than rooms, and `world/charter_move.py:207` takes its
no-scene branch — `travel_rooms(scene, origin, target) if scene else 1` — where
every hop costs 1 and always succeeds. Chat 93 moved 8 bodies that way; chat 84
moved none, and that difference is which windows ran, not geography.

So the two gaps restate:

* **There are no edges because there is no graph**, not because a record was
  the wrong shape. `travelled` is an odometer (`travelled[body] += rooms`), and
  with no scene every hop adds 1.
* **The namespace question is really a configuration question**: should an
  institution be given a charter scene at all, and if so, is it the chat's
  scene or its own? The code supports both and these worlds chose neither.

What survives unchanged is the bridge defect below, which is independent of all
of this: `background_presence_records` filters by PLACE, `agents/background.py`
queries with a ROOM id, and those never match whatever geography the
institution does or does not have.

## Options

**A. One namespace by construction.** The generator emits scene rooms under
charter place ids, so a place *is* a room. The bridge becomes structural and
the mapping problem disappears. Cost: every charter place must be depictable
as a room, which is false for an institution that models an office nobody will
ever enter; and the generator gains a constraint it currently does not have.

**B. An explicit place-to-room table.** A charter place may or may not have a
room depicting it; the table says which. Survives places that are never
depicted and rooms that belong to no institution. Cost: a third thing to keep
in sync, and a table that drifts silently is the defect class this whole
document is an instance of.

**C. Mint rooms at promotion.** On promotion, generate rooms for the places the
body knows and seed its graph. Cost: a mapping call per promotion, and it
invents geography late — the rooms exist because someone was promoted rather
than because the world has them.

None of the three supplies edges. Whichever is chosen, the route half needs its
own answer: either charter practice starts recording transitions (a body that
goes canteen → corridor → lab writes an edge), or a promoted body is seeded
with nodes and left to learn its routes by walking, which is honest but means a
lifelong employee navigates like a tourist for her first twenty beats.

## What is unknown

* **Whether charter bodies move between places at all**, or whether `place`
  is effectively static per body. `stood` tallies one post per body in the
  sample, which is consistent with either. This is the first thing to measure
  and it decides whether the edge problem is real or moot.
* **Whether a place-to-room correspondence is wanted at all.** It may be right
  for the charter world to remain an offscreen institution that surfaces only
  as presences, never as walkable geography — in which case the bridge should
  be fixed and the promotion transfer abandoned.
* **What a promoted body should be entitled to know.** A lifetime of working
  somewhere is not the same as having walked every room, and seeding a full
  graph would hand a mind knowledge it never earned — which is the firewall's
  own objection, applied to space.

## The cheap thing to do first

A diagnostic, not a fix: when a chat holds a non-empty charter registry and a
scene, and they share zero place/room ids, say so. It cannot fire falsely —
zero overlap with both sides non-empty is unambiguous — and it would have
surfaced this on chat 84's first turn instead of in a survey fourteen turns
later.
