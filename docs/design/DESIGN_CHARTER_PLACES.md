# The rooms the closure invents: where they stand and what they are called

Status: BUILT 2026-10-08, reviewed and repaired twice by 2026-10-09
(frontages for split siblings and annexes, judged on the plane; the
closure's measurements and marks; names dealt into the grammar's slots for a
dwelling's siblings and for a stretch whose axis names the kind; the split
report in the Room's review). The owner ruled two calls ON on 2026-10-08: a
street nobody measured is lengthened to hold what is split along it
(`FRONTAGE_MEASURES_STREETS`, "unmeasured stubs only"), and a split
dwelling's siblings are dealt proper names (`DEAL_SIBLING_NAMES`, over the
recommendation to keep the numbers). One is still the owner's and built OFF:
whether the plan specification tells the Room what a frame is
(`charter_generate.PLAN_EXPLAINS_FRAMES`). The register entry is
[`../UNBUILT_WORLD.md` §2.44](../UNBUILT_WORLD.md#unbuilt-2-44).

The owner chose this on 2026-10-08 from a procedural-generation scoping
study, under one rule: **a model decides what and why, code decides where and
how.** Nothing here decides what a place is for, what is in it, whose it is
or what it looks like.

## 1. Why

The charter closure (`world/charter_generate.close_plan`) already invents
rooms. `_spread_berths` splits a dwelling berthing more than `BERTH_CEILING`
sleepers into SIBLINGS -- same purpose, same neighbours -- and hangs a
workplace's overflow off it as ANNEXES. It finished none of that work:

* **No place.** A sibling copied its parent's doorways, so whichever wall a
  hand later gave the parent's street, every sibling was laid on the same
  stretch of it. Chat 165's opening put the Back Row and its four siblings on
  the cross walk's north wall; the doorway spread gave five fractions of one
  six-pace wall; the planar layout stacked all five. Measured on the stored
  scene: **19 standing plane-embedding rows, 8 naming a sibling**, and
  `site_plan.derive_site_plans`, which then refused a whole connected group
  on any clash, refused the town on **33 clashing pairs** (chat 166: 5). None
  of the play database's 957 rooms carries a site. (Since 2026-10-09 a plan
  is laid room by room: `DESIGN_SITE_PLAN.md`, "A plan derived room by
  room".)
* **No name.** A sibling or an annex took an ordinal ("the Back Row 2" .. "5";
  "The Plank Walk Spine 2" .. "30" in chat 164), and a frontier stub took its
  axis label. Chat 165's grammar carries eight `{name}` frames and nothing
  filled one: `structure.mint_frontier` handed them out as written, and the
  stored plan's own causeway axis "the mainland" mints a stub called **"the
  {name} Sheds"** (`the_name_sheds`) on the code this replaced, because every
  one of the eight frames opens on "the" and the article alone made each one
  eligible.
* **No measurement.** `close_plan` rebuilt every room through an allowlist of
  name, purpose, edges, frontier and fixtures, and dropped the rest: the plan
  specification asks every room for its `exposure`, the Room's review refuses
  a draft without one, and the closure threw it away. Chat 166's
  closure-planted pile houses reached the registry with no exposure, extent or
  storey, where the rooms a plot package planted beside them kept all three.
* **No report the Room could see.** Chat 164's planner berthed a port-labour
  population on its public walk; the closure hung 29 purpose-less annexes off
  that one room and said so in the host's launch warnings, never in the review
  the Room reads.

## 2. What code decides, and what it never does

Code writes only what the plan measures: a doorway's `offset` along its wall,
a bearing where nothing but the plan's own copy ever set one, and -- on the
owner's ruling, for a street nobody measured -- a street's `extent`. It never
adds a way between rooms (the owner's site-plan rule), never moves a bearing
a hand declared, never touches a room that carries prose, and never decides
a place's purpose, contents, owner or look. A dealt name goes only into a
slot the Room's grammar opened, for a kind the place was chosen to be: a
stretch whose axis names that rule's kind and was drawn to it, or -- on the
owner's ruling -- a sibling whose parent is named in that frame.

## 3. The closure: measurements, marks, the report

* `close_plan` keeps a drafted room's geometry through the same fail-open
  normalizer the package path uses (`plot_packages._plan_geometry`): extent,
  shape, exposure, sound, storey, what it lies over, floor, surface, quiet. A
  value the world cannot read is no value, and never a failure: `over` is a
  list of rooms (a bare string is one room, never its letters; `true` is
  nothing) and `floor` a word, so one malformed room no longer fails the
  Room's review or a launch.
* A sibling is measured like its parent (the parent's geometry less `over`,
  which names one room beneath the parent) and copies its parent's doorways
  less where on the wall the parent's door stands (`offset`, a pinned `cell`,
  a `passage` record): those are the parent's doorway, and a copy put every
  sibling's door on it.
* Each minted room is MARKED with the room it came from: `split_of` for a
  sibling, `annex_of` for an annex (`world/frontage.py`). The mark rides the
  planned spec (`plant_structure` keeps it), and the re-keying of a namespaced
  town and of a spent identity carries it -- and `over` with it, which
  planting had left on a ruin's spelling.
* `berth_split_warning` is the one sentence for a split, read by the host's
  launch warnings and by the Room's `review_location` notes. An annex's says
  what made it: a population posted at a room people work at sleeps there,
  and one that sleeps elsewhere names its `berth`. Said every time, not past
  some count: no new cap.

## 4. Frontages

A plan rarely says which wall a doorway is on -- the location contract asks
for none, and chats 164 and 165 planted not one bearing -- so the wall
arrives with whichever hand first declares one, usually the opening's
establish. The frontage therefore runs where the scene first holds that wall,
at the end of `structure.materialize_planned_fringe` on every commit, and
reads the marks from the plan:

* **A sibling stands along the street its own doorway is walled onto**, or
  its parent's only street, at the free run nearest the parent, its run kept
  inside the wall so it never overhangs the street's end. A sibling copied
  every street its parent fronts; where the parent fronts several and none is
  walled on the sibling's side, which one it stands on is a choice, so it is
  left and reported (it used to take the first in id order: a house whose
  parent fronted a lane and a garden was laid across the garden). Where
  nothing but the engine put the parent's door where it is (a stub's door
  whose own side carries no offset, standing nowhere else), the parent and
  its siblings are laid as one block, so a door the even spread set mid-wall
  does not strand the run either side of it.
* **The far side of the street** takes a sibling only where its bearing is
  still the plan's own copy and both rooms are the plan's stubs. A bearing the
  scene holds that the plan never wrote is a hand's, and stays: chat 165's
  siblings were walled by the establish, so they are moved only along it.
* **An annex takes a wall of its workplace no other doorway uses**; a corner
  doorway uses both walls it meets. While any of the workplace's own doorways
  has no wall yet, a wall-less annex waits.
* **THE PLANE IS THE JUDGE, NOT ONE WALL.** A run free along the street's
  wall can still be where a room laid through another doorway stands -- the
  side room off the parent's flank -- and the first build compared one
  wall's runs only, so it moved a sibling onto that side room, reported it
  placed and pinned it there. A place is now taken only where the room lands
  on no room at all, read both ways a plane is drawn (`_Plane`): the layout
  lint's (`layout_rooms`, group by group from the smallest unplaced id, a
  refused room standing where it would have landed) and the site plan's
  (`site_plan.plan_frames`, the layout `derive_site_plans` writes a plan
  with, so there is one copy -- since 2026-10-09 room by room, a room it
  refuses standing in the frame where its first doorway would have put it). A choice looks past the rooms still waiting to be
  laid in the same pass, which may yet move. A room alone on its wall but
  standing on another room is never written down where it stands; the plane
  is read again once everything has moved, and a moved room that lands on
  any room is put back and reported (`lands_on_a_room`) -- a sibling the pass
  left where the doorway spread put it included: the second build passed
  those over, and a sibling was moved onto the one beside it, reported
  placed and pinned (40 of the 234 constructed lanes in the second review's
  sweep; none now). A parent slid along its wall to make room for a block of
  its siblings goes back once none of them stands placed: it was moved for
  them.
* **A room given its place carries its offset and is left alone thereafter**;
  a room that already stands clear has its place written down unmoved, so the
  doorway spread cannot move it when the wall gains a door.
* **What does not fit is left where it stands and reported** (`lay_frontages`'
  rows: placed, far side, measured, unplaced, how many paces short, and the
  streets a sibling could front).
* **`FRONTAGE_MEASURES_STREETS` (on, the owner's ruling: "unmeasured stubs
  only")**: a street nobody measured that is still a stub is given an extent
  long enough to hold every room on that wall side by side, at most
  `EXTENT_MAX_PACES`. A longer street moves every room laid through its other
  walls too, so a measurement is made only where every room it lays then
  stands on no room and no other room stands on one it did not stand on
  before, and where any room it laid is put back afterwards it is taken back
  whole, the street's length with every doorway it wrote. The second build
  compared each room only with what it already touched, so a stranded sibling
  that touched a side room by a column was laid fully onto it, then put back
  while the street kept the length measured for it (84 of the 486
  constructed cases in the second review's sweep; none now). A street the
  Room measured is never lengthened at run time: the fringe re-applies the
  plan's measurement to a stub every beat.

Measured offline on the stored scenes (the marks reconstructed from the
closure's own `<berth>_<n>` minting, since these towns were planted before
the marks existed; no model call):

| | rows naming a split (all rows) | derive clash pairs | sites placed |
|---|---|---|---|
| chat 165, before | 8 (19) | 33 | 0 |
| chat 165, flag off | 8 (19) | 33 | 0 |
| chat 165, flag on (the ruled default) | **0** (15) | 18 | 0 |
| chat 166 (all three frames), before = after | 0 (8) | 5 / 4 / 5 | 0 |

With the flag on, as ruled, chat 165's cross walk is measured to 30 paces
and all four of the Back Row's siblings stand along it, and the plane check
takes nothing back. Off, it changes nothing measurable, and that is the honest
result: the cross walk is unmeasured, so it is the six-pace square the engine
draws a room as, and the Back Row alone fills its north wall; the main walk
is a room the story has entered, whose doors are its author's. What still clashes in chat 165 is
the establish's own geometry -- three rooms on the cross walk's six-pace east
wall, three on the main walk's, the boat shed, the drying racks -- plus the
main row's one sibling, stacked on its parent on the developed main walk.
Chat 166's siblings have no bearing onto either walk, so there is nothing to
front; its five pairs are the Room's and the Director's (the boat sheds on
the Gale house, the drying racks on the low and market walks, the landing
stage on the reed flats, the Gale house landing on the low walk). Chat 164
never opened; walled hypothetically by the engine's own bearing derivation,
its walk's eight planned neighbours take all four walls and four corners, so
**0 of its 29 annexes** can stand on it -- the ceiling the report names.

Cost, this build and the second timed side by side on one machine
(2026-10-09); one read of chat 165's plane takes about 30 ms. A pass that
finds no free run reads no plane (one whose free runs all land on a room, or
whose measurement the plane refuses, reads it once or twice every commit: 14
of 375 fuzzed configurations, up to about 0.25 s a commit on chat 166): chat
165 with the flag off, 40-42 ms while its five siblings wait (39-44 ms
before); chat 164, about 50 ms. The pass that measures and lays chat 165's
cross walk reads the plane three times, about 0.18 s once, and every pass
after it about 15 ms. Where the siblings' doorways onto the cross walk are
still unwalled -- a hand walled the parent and not its copies -- the second
build read the plane before every change of wall and threw the read away on
the next line: twelve reads, about 0.5 s, every commit, for nothing placed.
This build reads it none: 37-40 ms. A pass with nothing waiting writes
nothing.

## 5. Names

A grammar name may be a FRAME with a `{name}` slot. Whether the plan
specification says so is the owner's call, and OFF (`PLAN_EXPLAINS_FRAMES`):
a Room writes frames unprompted -- chat 165's grammar is eight of them --
and the engine fills them either way. On, one sentence tells the Room that a
frame is never a room's name as written, and that the engine fills its slot
only in a room plainly of that kind -- a further room of a dwelling it
splits, where the dwelling is named in the frame, or a further stretch of a
frontier, or a frontier named only by its bearing, whose label names the
kind. The first two builds read the sentence to every location pass with no
switch, saying the slot was filled "where nothing leaves the kind in doubt",
which was untrue under the defaults they shipped with.

* **A frame is whole words where it spaces its slot off.** "the {name} Row"
  matches "the Back Row" and not "the Sparrow", "the Barrow" or "Theatre
  Row"; "the {name} Way" does not read "Cause" out of "the Causeway". A frame
  that writes its slot against its text ("{name}長屋", "{name}ton") is filled
  against it. The first build joined slot and text with an optional space,
  so a boarding house called "the Sparrow" read as a row called "Spar" and
  its siblings were dealt row names.
* **A frame is never a name as written**, and a word every grammar name
  shares cannot make one eligible -- the article that made all eight of chat
  165's frames eligible. (A word every RULE shares raised every rule's
  affinity alike and changed no choice; the first build subtracted it anyway,
  and that subtraction is gone.)
* **A frontier stub is dealt a name only for a kind its axis names**: where
  it would otherwise be named by an ordinal (a later stretch of one axis) or
  by a bare bearing -- neither is a place's name -- and the axis names that
  rule's kind more than any other rule's, by a word of its `kind` or one its
  frames do not all share, and the rule was drawn alone. A rule drawn at
  random -- no word in common, or a tie the seed breaks -- is a kind nobody
  chose, and each stretch of one axis could draw another; the first build
  dealt that guess into the name every mind reads ("the mainland" ran The
  Mainland -> "the Fennasted Way" -> "the Hollaholm Row"). A purpose names no
  kind either: it is prose, and its articles and prepositions are words like
  any other, so the second build, which read every word of a rule, drew the
  row rule for "the far end of the walk" by "the", "of" and "walk" and dealt
  its second stretch "the Holawick Row". The words every one of a rule's
  frames writes say how the story frames a place of that kind ("the {name}
  ..."), not which kind it is, so they ask for nothing, and a rule with one
  frame is asked for by its `kind` alone. The guess stays in `purpose`, which
  reaches the Director's brief and no mind, and the stretch keeps its
  ordinal. An axis the planner named keeps its name: it is the planner's word
  for what lies that way.
* **A dealt name renames the room and never re-keys it**: the uid stays the
  one minted (`far_walk_2`), as a named sibling keeps `back_row_2`. A uid
  re-derived from a kana name was the empty id -- the registry gained a row
  keyed '' and the holder recorded its axis as spent into it.
* **A split dwelling's siblings are named in their parent's frame**, on the
  owner's ruling of 2026-10-08 (`DEAL_SIBLING_NAMES`, over the
  recommendation to keep the numbers): a sibling whose parent's name is an
  instance of a frame ("the Back Row" of "the {name} Row") is dealt a word in
  that frame -- one planned row becomes several named rows -- held apart from
  every body every charter berths, exactly and at the similarity floor. Where
  no word survives the refusals the ordinal stays; off, every sibling keeps
  its ordinal.
* **An annex keeps its ordinal**: it has no kind, so no frame is its own, and
  a frame borrowed from its workplace would claim it is another workplace.
* **Segments of one way are named, not described.** "Further along the spine"
  was considered and refused: it is English the mint cannot write in the
  story's language, and a relative name points the wrong way from the far
  end.

The word comes from the story's own naming lanes, never blended
(`world/place_names.deal_place_name`): at the closure, the author's law alone
when there is one, else each charter's law -- the same fragments the launch
writes back as this story's phonology; at the frontier mint,
`story.naming.story_naming_lanes`. Seeded by the structure key and the room's
uid, so a reroll renames nothing, and no model is asked. A WORD is refused
when it reconstructs a reserved name (`reconstructs_a_reserved_name`), equals
a reserved element or reads as one at Jaro-Winkler 0.88 or more
(`NAME_SIMILARITY_FLOOR`, the owner's 2026-08-28 ruling, built for this);
when it equals or reads as a word of a resident's name -- the charter
registry's people at the frontier, the plan's bodies at the closure (the
first build passed the frontier none, and refused residents only exactly: it
dealt "the Marlaburn Row" to the room the Marleyburns sleep in, at 0.94); or
when it equals, reads as, or opens on the same four letters as a place word
already standing in the grammar's frames (`NAME_PREFIX_FLOOR`, the prefix
veto ruled with the two floors: "the Drayelburn Row" beside "the Drayamere
Row" was below 0.88 and still one row misheard). A NAME is refused when a
room already answers to it, compared by its letters in any script
(`spelling_key`) and by the engine's room fold (`normalize_room_id`): the
first build compared the fold alone, and every kana name folds to the same
empty id, so a kana story never had a name dealt. After `PLACE_NAME_ATTEMPTS`
(32, the person mint's own number) the fallback stands.

Measured offline on chats 164-166:

* **Chat 165, siblings, as ruled**: "the Drayelburn Row", "the Cularhook
  Row", "the Quayeywick Row", "the Rusheyhook Row" and "the Culoley Row",
  identical on a rerun, none within 0.88 of any of its 103 residents' name
  words (the closest, 0.859) or of a reserved name (the first build's "the
  Marlaburn Row" and "the Drayamere Row" are refused). Off: "the Back Row 2"
  .. "5" and "the Main Row 2", as before.
* **Chat 165, frontier**: its one real axis, "the mainland", keeps "The
  Mainland 2" .. "4"; so do all 24 later stretches of the eight axes the
  first review probed (the row and shed rules' purposes say "the walk", so
  "far walk" names the walk rule and is drawn to a three-way tie), and so do
  the axes the second review found drawing a kind from a purpose's prose --
  "the far end of the walk", "out over the reeds", "the end of the line"; its
  bearings keep "North", "East", "Down" (the first build dealt all 24 and the
  three bearings, one of the 24 a resident's own family name and five within
  0.88 of one). Six axes that name a kind ("the herring stage", "the far
  float", "the net sheds", "the old houses", "the pile row"; "the reed walk"
  is drawn to a tie) name 15 of their 18 later stretches, none equal to or
  within 0.88 of a resident's word.
* **Chats 164 and 166**: unchanged. 164's grammar has no frames, so its 29
  annexes and three other splits keep their ordinals and its stubs their axis
  labels; 166's grammar is empty.

## 6. What is left

Registered in [`../UNBUILT_WORLD.md` §2.44](../UNBUILT_WORLD.md#unbuilt-2-44):
the plan specification's frame sentence is the owner's, and off; a street the
Room measured is never lengthened here; a sibling whose doorway has no wall
yet is not counted when its street is measured; what does not fit is
reported only through the layout lint's own rows at run time, and is tried
again every commit; a developed street's doors stay where their author put
them; the frontage reads only rectangles; existing towns carry no marks;
affinity reads words a space separates, so an axis in a script without
spaces rarely names a kind, the draw still reads every word of a purpose so
a purpose that mentions another kind ties it, and a word only some of one
rule's frames write, or a kind written with an article in it, still asks;
the person mint does not yet use the similarity floor.
