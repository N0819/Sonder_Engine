# Unbuilt work — Living world and institutions

Part of the [unbuilt-work register](UNBUILT.md). Entries are grouped by status
and retain their original stable ids. Delete an entry in the same commit that
lands it.

## 1. Known defects

<a id="unbuilt-1-10a"></a>

### 1.10a A charter body promoted to a character knows nothing about where it is

Two disjoint gaps, argued in
[`docs/design/DESIGN_CHARTER_SPATIAL_PROMOTION.md`](design/DESIGN_CHARTER_SPATIAL_PROMOTION.md).

A place graph's nodes are keyed by ROOM ID and its edges are written by
walking (`world/place_purpose.py`: "a node needs a rid, hearsay carries none").
A charter body carries `place` / `berth` / `home_post`, and its movement record
`stood` is a TALLY at a post — `{"canteen_supply_duty": 34}` — not a path.

CORRECTED after measuring, and the correction matters: this is NOT a namespace
mismatch between charter places and scene rooms. An institution carries its OWN
optional geography at `charter["scene"]` — `world/charter_run.py:420`, "A scene
is optional. Without one the institution is a single place and everyone can
stand any post" — and NONE of the four charter worlds in the corpus (chats 84,
83, 93, 94) has one. Their places are labels on a flat institution;
`world/charter_move.py:207` takes its no-scene branch, where every hop costs 1
and always succeeds; and `travelled` is an odometer, not a route. So there are
no edges to transfer because there is no graph to have edges in. The real
question is configuration: should an institution be given a charter scene at
all, and is that scene the chat's or its own?

Same cause, separate defect: `agents/background.py:320-333` asks which charter
bodies are near by passing the player's ROOM id to
`charter_runtime.background_presence_records(cid, places=...)`, which filters by
PLACE. The intersection is always empty, silently, inside a bare
`except Exception`. This is why the charter system reads as unexercised — the
scene has never contained a place its 37 bodies live in.

Cheapest first step is a diagnostic, not a fix: a non-empty charter registry
and a scene sharing zero ids is an unambiguous dead bridge and can be said so.

**PROTOTYPED 2026-09-02, on `main` since 2026-09-03** (`e907c7a7`;
`tests/test_charter_traversal.py`). The prototype answers the second half of
this entry -- the route half -- on a charter that HAS a graph, and leaves the
first half (no live charter world has one) exactly where it was. As built: a
charter body carries the courier's shape between windows
(`world/charter_move.py`: a route planned once over the shared pathfinder, a
leg, `place` always the current leg's room), a window buys
`WALK_ROOMS_PER_HOUR` rooms per hour (the courier's own walking pace, 6), a
shut door holds a body where it stands with no re-plan, every edge walked is
recorded per body in room-id vocabulary (`charter["walked"]`), and
`charter_promote.inherited_place_graph` seeds a promoted body's
`chat_chars.state.place_graph` with the town's PUBLIC rooms (every room that
is not somebody else's berth, basis `told`) plus the rooms it walked (basis
`walked`, visits counted). Measured on `charter_worlds.big_town`: the same
64,035 rooms crossed in both arms, 53.0s before against 52.8s after on 300
bodies over 720 hours, once the walked record stopped being deep-copied
per window (77s before that fix). What the prototype does NOT do, and what
argues against calling it finished: the dispatch pace (24 rooms per
four-hour window) means nearly every walk on a settlement-sized map finishes
inside the window it began, so the transit state is exercised only by a short
window or a long road; `REACH_LIMIT` still decides reachability by count
rather than by the pace; "public" reads a private interior nobody berths in
as public; inherited nodes carry no bearing; and no live charter world has a
scene for any of it to run on, which is the configuration question above and
is still open.

**THE CONFIGURATION QUESTION IS ANSWERED, 2026-09-02, and the answer was
already in the code.** A generated institution is given the planted skeleton
as its scene, composed under the live scene: `advance_snapshot` had been
doing exactly that on the first in-play catch-up all along (measured on the
Harrowmere playtest: 20 rooms after turn 9, 27 by the end, 371-474 walked
edges per working charter), so the four scene-less corpus charters are
worlds generated before a skeleton was planted, not a rule. What was still
missing was PRESIM: `presim_registry` ran with no scene, so the whole 720h
prehistory was teleports (`travelled` = 1 per body). `plant_structure`
precedes presim, so it is one argument -- `presim_registry(scene=
charter_runtime.skeleton_scene(rooms))` -- and the prehistory now walks the
town's own graph: on the Harrowmere plan closed at 100 residents, 8,193
walked edges over 91 bodies against 55, for 6.5s against 5.7s, replay
byte-identical (`tests/test_presim_walks_the_skeleton.py`). The route half
above stays a prototype's; this closes the half that had nothing to run on.

**THE WITHIN-ROOM HALF LANDED 2026-09-05** (`world/charter_place.py`,
`docs/design/DESIGN_CHARTER_PLACEMENT.md`, `tests/test_charter_placement.py`).
A body had a `place` and nothing inside it: perception graded it by room (a
townsperson behind a screen was seen), `charter_observe` stood the observing
body in its room with no cell, the movement floor never route-checked a
Director move of one, and such a move committed as a second positions row.
Now a body stands at its authored `station`, its post's `anchor`, the doorway
toward its next walk leg, or a cell dealt from (identity seed, room) -- laid
on a shallow view of the scene, never stored -- and a Director
`positions`/`stations` entry naming it is routed to the body record inside
the commit. Measured at Harrowmere scale: 10 bodies laid in 1.7ms per beat
for the observed frame, 100 in 12.6ms for the evidence pass. The map half
landed the same day (`web/world_routes.py`'s `charter_body_records` and the
charters router, `static/js/world_browser.js`;
`design/DESIGN_CHARTER_PLACEMENT.md` § The map). Residual, and not a defect:
inherited place-graph nodes still carry no bearing.

<a id="unbuilt-1-30"></a>

### 1.30 The background-claims lane has fired seven times, all one way

**Updated 2026-08-18.** The entry used to read "has never once fired", and that
was true when measured 2026-08-08: 0 claims across 17 chats playing at
`scene_life=full` over 2,114 turns and 46 tracked presences. Re-measured
read-only against the live database, the lane has now produced **7 claims, all
7 ratified, 0 contradicted, 0 expired**, in one chat.

Seven is not evidence the lane works. Until `5ab591e` `_verdicts` inferred
adoption from any four-character reference appearing anywhere in the resolved
event of the beat being settled, and `background_react` runs AFTER
`director_resolve` — so the text was written before the presence spoke, every
claim settled on the beat that produced it, and contradiction and expiry could
not fire. A three-outcome design collapsed onto its one irreversible branch,
and it is invisible because ratification is the branch that looks like success.
Inferred adoption now requires a LATER beat. **The seven rows stay** (owner
decision 3): canon is write-once, and repairing persisted story data is the
owner's call. Two of the seven carry a raw engine uid as a speaker and one
establishes a DENIAL as truth.

So the fire rate still has to be measured, on a run under the repaired gate. A
lane whose only firings happened through a defect gives no chances, not a
rate.

Why, structurally: a claim only enters the lane when `scene_life` output
survives `_claimed_refs` -- either the model volunteers `asserts` (it never
has) or `novel_proper_nouns` finds a capitalized phrase not already in
`_known_world_names` (managed presences mostly answer about things already
named). Nothing else in the engine mints claims. The lane is therefore held
shut by prompt compliance alone, in both directions -- nothing enters it, and
if something ever does, the read-back path it ratifies into is **ungated**:
`write_canon` writes `category="other"` rows, `knowledge_for_character` gates
only `category="knowledge"`, `search_lore` has no observer parameter, and the
audience known at mint time is discarded, so a future per-mind gate cannot be
built on the read side without re-plumbing provenance through
`canon_provenance` (currently written and never read by anything epistemic).

For whoever builds the lane's first real producer (the generated-gossip plan):
land the producer and the read-side gate in the same change, or the first
claim ever ratified becomes knowledge every mind in the chat reads back
without having been in the room for it. And re-measure the fire rate after --
a lane that has never fired gives `no chances`, not 0%, and the first nonzero
denominator is the first evidence the mechanism exists.

<a id="unbuilt-1-84b"></a>

### 1.84b A ship with three captains: a rotation applied to a post that cannot rotate

`world/charter_generate._ensure_shift_crews` tops EVERY post to a three-body
rotation. Measured on a generated starship, read from `item["state"]`:

    captain                3   Tasha Ishikawa, Jack Picard, Rene Soong
    first_officer          3   William Crusher, Keiko O'Brien, Rene Crusher
    conn_officer           6
    chief_engineer         3   Miles Guinan, Beverly La Forge, Geordi Barclay
    chief_medical_officer  3   Reginald Pulaski, Deanna Crusher, Katherine Crusher

Three conn officers across three shifts is what a rotation IS and is correct.
Three captains is not a rotation, it is three captains — and with a registered
captain also in the story, four people answered to "Captain".

**A POST'S TITLE IS AN ADDRESS.** This is `address_components`' own rule applied
to rank instead of to a name: a component is identity where the law lets it
stand for the whole person, and everyone on that deck calls the captain
"Captain". Two bodies holding one such post is the same defect as two bodies
sharing a name — one word resolving to two minds.

**Half of it is now SEEN, none of it is yet PREVENTED (2026-08-28).**
`charter_runtime.registry_warnings` names a root post held by more than one
body — the `reports_to` signal below, read for cardinality — so a generated
charter says so on the day it is authored instead of fifty beats later. It is a
warning and stays one: co-equal roots are legitimate, and validation here never
rewrites a Charter. What is unchanged is the generator: `_ensure_shift_crews`
still tops every post to three, so the charter that emits the warning is still
the charter that gets minted. Fixing that is this entry's own work and needs
1.84c's constraint nowhere near it.

**PREVENTED AT THE GENERATOR, 2026-09-02.** `charter_generate._post_seats`
fixes a post's headcount three ways, honoured in order: an authored `seats`
(1.84e's shape (a), posts gain a headcount), an authored `singular`, or being
a HEAD -- `_head_posts`: a post nobody reports past AND somebody reports to,
a post reporting to itself counting as reporting to nobody, because planners
write the top of a chain that way. A lone post (the smith of a one-post
smithy) has no subordinate and is a watch, not a head. `_ensure_shift_crews`
now trims a fixed-seat post to its seats as well as topping to them, from
the highest generated index down and never a featured resident. Measured on
the Harrowmere plan: the reeve and the innkeeper hold their offices alone,
their clerks and brewers still rotate in threes. `HEAD_SEATS` = 1, named
where the other closure numbers are. 1.84c is untouched: how a holder
CHANGES is still the owner's. `tests/test_charter_closure_invariants.py`.

The signal to tell a rotating post from a singular one is ALREADY IN THE DATA
and needs no new field: `captain` carries `reports_to: ""`. A post nobody
reports to is the root of the tree, and a chain of command with three tops is
not a chain. Department heads are the softer case — a chief engineer plausibly
has shift deputies — but a deputy is a deputy, and the title says which.

<a id="unbuilt-1-84c"></a>

### 1.84c Succession — OWNER'S DESIGN, not to be specified here

The constraint, stated by the engine's owner: **a top rank is replaced only by
retirement or death.** That is the whole of what is settled.

Everything else about succession is theirs to design and is deliberately NOT
written down here — an earlier revision of this entry specified the rule, the
event shape and the failure modes, which was overreach. The nuance is the
subject: what relief-of-command is against death, whether an acting holder is a
holder, what happens to a post whose holder is present but incapable, how a
chain re-forms under it, and whether any of that is the same event as the
background-presence replacement in 1.84a's naming note. None of those follow
from the constraint, and guessing at them produces a design that looks finished
and is not.

RECORDED SO IT IS NOT LOST, AND SO NOBODY BUILDS IT BY ACCIDENT: the uniqueness
half (1.84b) can land on its own — a singular post holding one body is
enforceable from `reports_to` alone and needs no theory of how holders change.
Do that; leave this.

<a id="unbuilt-1-84d"></a>

### 1.84d A character has nowhere to carry a rank, so the rank goes in the name

`identity` on a character sheet holds exactly `aliases`, `name`, `pronouns`,
`uid`. There is no field for a rank, title or honorific, so a generator asked
for a ranked character puts the rank in the only field that will hold it.
Measured across generations from the same briefs: `Lieutenant Commander Data`,
`Worf, son of Mogh` — a rank and a patronymic, both sitting in `name`.

THE ASYMMETRY IS THE EVIDENCE. A Charter body carries `rank` as its own field
(`{"key": "captain:0001", "name": "...", "rank": "captain", "home_post":
"captain"}`), and a naming law carries `titles.ranks` mapping post keys to
display titles. So an institution can express rank and a registered character
cannot — which is why placing a cast member into a post needs a rank supplied
from outside their sheet, and why `{title} {name}` renders correctly for a
generated body and not for a cast member whose title is already inside `name`.

WHAT IT COSTS, beyond tidiness. Name IS identity here: `scene.positions`, the
active cast, addressing, perception routing and every psychology write are keyed
on it. A key with a rank baked in means:

  * the reservation that stops a generated body taking a registered identity
    holds `"lieutenant commander data"` and not `"data"`, so a component check
    had to strip titles to recover the person — a downstream compensator for
    an upstream gap (`world/charter_identity.name_is_reserved` now compares
    against the untitled runs for exactly this reason);
  * a promotion, demotion or transfer changes the key a mind is addressed by,
    which is the same class as 1.84a's name-permanence problem;
  * two stories that disagree about whether to include the rank produce two
    different keys for one character.

`aliases` is not the answer: it is for names a person is also known by, not for
a rank that is orthogonal to their name and changes independently of it.

Not built, and not obviously small — every reader keyed on `identity.name`
would need to know which part is address and which is identity, which is the
same distinction `address_components` already draws for a naming law.

<a id="unbuilt-1-84e"></a>

### 1.84e An institution with no members below its posts — OWNER'S CHOICE OF THREE SHAPES

1.84b's complement, and the half a fix to 1.84b would not touch. It is not only
that a singular post got three holders; it is that the institution has NO
MEMBERS BELOW ITS POSTS AT ALL. Capping the root post at one body would leave
chat 95 with 22 command-tier officers and still no rank-and-file.

Measured, chat 95's generated `starfleet_crew`, from a brief asking for a
thousand people on three shifts: **24 bodies across 7 posts in 5 rooms**,
`home_post` non-empty for all 24, and rank a strict function of post — 7 posts,
7 distinct (post, rank) pairs: 3 captain, 3 commander, 11 lieutenant_commander,
7 lieutenant. The charter's own `naming.titles.ranks` defines six rungs;
`ensign` and `lieutenant_junior_grade` are carried by zero bodies and are
**unreachable by construction**, because the only way a body acquires a rank is
to be minted into a post and no post carries those titles.

AN INSTITUTION MODELLED ONLY AS ITS COMMAND POSTS HAS NO RANK-AND-FILE, AND A
HIERARCHY WITH NO BASE IS NOT A HIERARCHY. Where the only way to become a
member is to be minted into a post, membership size is bounded by post count
times the rotation floor and every member is by construction whatever the top
of the ladder is. An institution whose whole staff is its own org chart has
been described, not populated.

WHERE IT ORIGINATES, and it is not the data model. `charter_model.normalize_
body` already tolerates `home_post: ""` and already carries `rank` as free
presentation metadata independent of post — rank is decoupled from post in the
SCHEMA and welded to it in GENERATION. `charter_generate._PLAN_SYSTEM`'s output
schema line is `populations:[{post,count,competence,berth,rank}]`: a population
is DEFINED as a group attached to a post, so the plan has no way to describe a
member who holds none. Reinforced twice downstream — the prompt asks for "at
least three people for each post", and `_ensure_shift_crews(crew_size=3)`
guarantees it deterministically. Every body-minting site in `close_plan` keys
the body to a post (`f"{post}:{index:04d}"`, `home_post=post`), and a
population naming no post is given a synthesized one (`f"role_{pi+1}"`).

`scale` did not save it. The payload carries the brief's scale and the prompt
tells the model to "fill out the support infrastructure needed for that scale"
— that clause is about ROOMS. Nothing ties membership size to scale, so "at
least three per post" became the ceiling.

The prose consequence is downstream and blameless. `charter_crowd.members_of`
returns 10 bodies for the bridge, `count_band(10)` is "a dozen or so", and
`composition_of` tallies `title_for` per member: **"a dozen or so captains and
commanders pulling transit watch"** reached the Director and the narrator in
the PAYLOAD on all 16 turns. Blanking rank at the mint would not help either —
`charter_identity.title_for` falls back to `titles.posts[role]`, so a rankless
body standing the top post still reads as that office. No fix exists downstream
of generation; every renderer is individually correct and faithfully reports
what the membership IS.

**LANDED 2026-08-28: the detector only.** `registry_warnings` now names an
institution whose every body holds a post while its bodies outnumber its posts
and rank follows the post, and names any rank the naming law defines that no
body carries. Warnings, never rewrites — a small institution legitimately is
all offices, which is why the tell requires REPLICATION (more bodies than
posts) and not merely "everyone is posted". Chat 95's charter emits all three
of the membership warnings today.

**THE SUBSTANTIVE FIX IS THE OWNER'S, because three shapes are available and
they are not interchangeable:**

  (a) **POSTS GAIN A HEADCOUNT.** `normalize_post` grows a seats field, the
      plan asks for it, `_ensure_shift_crews` tops to it. Fixes 1.84b directly
      and cheaply. Does NOT produce a rank-and-file: it makes more top-post
      holders legal, not more junior members exist. *Landed at the closer
      2026-09-02 (`_post_seats` reads `seats`, and a head defaults to one);
      the plan prompt does not yet ask for it and `normalize_post` does not
      carry it, so it is an authoring tolerance rather than a surface.*
  (b) **UNPOSTED MEMBERS EXIST.** A population may name no post and mint bodies
      with empty `home_post` and an authored rank. `normalize_body` already
      tolerates it and `charter_plan` already staffs by competence, so the data
      model needs nothing — only the plan prompt and the generation vocabulary
      change. The only one of the three that answers "where is the base", and
      the cheapest per body.
  (c) **RANK DECOUPLES FROM POST**, becoming its own distribution over the
      membership rather than a population attribute. Largest change, and the
      one that makes promotion, seniority and 1.84c's succession expressible.

They compose. What the measurement settles is only that (a) alone is not it.

BLAST RADIUS OF ANY OF THEM, because membership size is an input to more than
prose: `charter_plan` staffing and its scarcity ordering, `charter_crowd.count_
band` (a crowd band IS a headcount), `charter_feel` strain means,
`charter_economy` consumption, `charter_history` prehistory volume, and presim
wall clock (~1.8 ms per simulated hour, `EXPERIENCE_CAP` 4000 rows per body). A
thousand-body institution is a different performance regime, not a bigger
number — which is an argument for (b)'s cheap ground over (a)'s headcounts, not
a decision.

Related and NOT to be built on top of by accident: 1.84b (the singular post),
1.84c (succession, owner's design). `docs/design/DESIGN_TOWN_GENERATION.md` §5
records the same missing primitive from the other side — deep facilities
needing "local sub-populations who live where they work".

<a id="unbuilt-1-95"></a>

### 1.95 A crew who have served together for years begin as strangers

The `known` ledger for a five-character bridge scene, read live after eleven
beats:

    {"Sabine Oyelaran": ["Lieutenant Commander Data",
                         "lieutenant_commander Lieutenant Commander Data"],
     "Worf":            [the same two],
     "Beverly Crusher": [the same two],
     "Geordi La Forge": [the same two],
     "Jean-Luc Picard": [the same two]}

Every mind in the story knows ONE other, and it is the same one. Nobody knows
the captain. The captain knows nobody. These are five officers who serve on one
watch.

RECOGNITION IS NOT THE BUG — it works. `_proximity_labels` checks
`_recognizes()` BEFORE sight level, so a known body gets its name even as a
silhouette. There is simply nothing in the ledger to win with, because the
engine has no notion of PRIOR ACQUAINTANCE at story start: `known` begins empty
and fills only from introductions that happen on the page.

WHAT IT COSTS, and this is what makes it worth fixing rather than tolerating.
In a dim room every colleague renders as "a shape" or "an indistinct figure";
in a lit one they render as an appearance epithet, "the lean middle-aged man".
Neither is a person, and a reader watching a crew address each other as
silhouettes for eleven beats is watching the firewall applied to a fact nobody
in the fiction is missing.

Two things are separable here:

  1. **ACQUAINTANCE IS DERIVABLE FROM THE CHARTER AND IS NOT BEING DERIVED.**
     The engine's owner's rule, and it needs no new authoring surface: bodies
     presimulated together in one institution KNOW each other, and everybody
     knows who is in command. The Charter already holds every input:

         reports_to: ""      the root of the tree. COMMAND IS PUBLISHED --
                             nobody needs to have met the captain to know who
                             the captain is, and that is what a chain of
                             command IS.
         reports_to: <post>  each body's own superior and subordinates. You
                             know who you report to and who reports to you.
         serves: <watch>     bodies on one watch have stood it together for the
                             whole presimulated horizon.
         authority           who may give an order, which is the other half of
                             knowing who commands.
         charter_run.run     already accrues `stood`/`travelled` per body across
                             the prehistory, so co-presence is recorded rather
                             than assumed.

     Senior posts know each other most strongly: they are few, they are in each
     other's chains, and the presim ran them together. Generics on DIFFERENT
     watches may legitimately not know each other -- that is a real gap in a
     thousand-person ship, not a defect -- but they all still know who is in
     command, because that is published rather than met.

     A cast attached to a story WITHOUT a Charter is the other case and still
     needs an answer; it is not this one. Note the shape exists elsewhere:
     `story/journey_history` seeds prestory MEMORIES before turn 0, so a
     pre-play seeding lane is not a new idea.

  1a. **THE PRESIM ALREADY BUILT IT, AND NOTHING READS IT.** Not a proposal --
     a measurement. `charter.state.minds` after a 720-hour prehistory of one
     institution: **42 heads carrying about 14 claims each**, while the story's
     `known` ledger for the same chat holds ONE name.

     One head, verbatim:

         ["captain:0002", {"body": "captain:0002",
                           "competence": {"command": 5, "leadership": 5},
                           "believed_available": true,
                           "strength": 0.7189166666666664,
                           "as_of_hours": 692.0,
                           "heard_from": null}]

     That is acquaintance AND reputation, with everything a belief needs:
     `strength` is a confidence that decays, `as_of_hours` is when it was
     learned (hour 692 of 720), and `heard_from` is who told them -- so a claim
     can be second-hand and its teller is recorded. Bodies carry claims about
     the FEATURED resident too (`captain:featured:...`), which is a registered
     character: the crew already know their captain in the Charter's model and
     cannot in the story.

     `world/charter_mind.hear_claim` is "THE ONLY UPTAKE DOOR" and routes
     body-to-body talk and authored tellings alike -- thinned by retention,
     scaled by the listener's regard for the teller, refused below a floor,
     never overwriting a stronger holding. `charter_run.py:549`: "witnessing,
     sighting and talk all put claims into heads."

     HONEST QUALIFICATION: these claims are COMPETENCE-shaped -- who is good at
     what, and are they available -- not free-text rumour. What exists is
     professional reputation rather than gossip. But the fields a rumour needs
     are the ones already present, and the uptake door is already shared, so
     the question is what a claim may CARRY rather than whether the machinery
     exists.

     So the gap is not that acquaintance must be derived. It is DERIVED,
     persisted, and stops at the Charter boundary. Whatever connects it has to
     answer one firewall question and only one: a claim is a BELIEF, held at a
     strength, possibly second-hand and possibly WRONG. It must arrive in a
     mind as a belief and never as a fact -- which is the same distinction
     `canon_provenance` already draws for an unadjudicated assertion.

  2. **A SILHOUETTE STILL SHOWS A PERSON.** Even with no acquaintance at all,
     the degraded label discards what a silhouette genuinely delivers, and the
     engine already holds all of it: `stations.at` (`captains_chair`,
     `ops_station`), `poses` (`seated`, `standing`, with `detail`), and `build`
     -- which the body-fields work made unlocated and whole-body precisely
     because no garment can cover it. "The tall one at tactical" and "someone
     seated at the command chair" are available today and subtract nothing;
     "a shape" is a person deleted.

`agents.perception._AMBIGUITY_CUES` lists "a shape" as a phrase the engine
DETECTS as hedging, which means nothing emits it from a template -- the narrator
writes it freely when handed an unresolved body. So half of (2) is a labelling
fix and half is what the narrator is given to work with.

ALSO VISIBLE IN THAT LEDGER: `"lieutenant_commander Lieutenant Commander Data"`
-- a rank prepended to a name that already carries one, stored as a RECOGNITION
KEY beside the unprefixed form. 1.84d's rank-in-the-name defect is now minting
duplicate identities in the ledger that decides who you know.

**THE OTHER CASE — a cast attached with no Charter — now has ONE writer and a
notice, and still has no authoring surface (2026-08-28).** Three paths create a
cast membership from nothing, and they held three different recognition
semantics with opposite defaults, none of them named anywhere: the greeting
launch seeded the player's edge with `already_known` defaulting TRUE, the
attach route seeded it with the same flag defaulting FALSY, and background
promotion seeded unconditionally and mutually across the whole active cast.
(Archive import and branch/clone copy the `world` table wholesale and so carry
`known` across faithfully; they never create a stranger.)

AN ATTRIBUTE NOBODY OWNS CANNOT BE DEFENDED — where several paths create the
same record and only some establish a derived invariant, the invariant is a
coincidence of which door was used. Recognition is a CHANNEL, and a membership
created without deciding its edges asserts, silently, that no channel exists.
All three now write through `commit_common.seed_mutual_recognition`, each
stating its own answer at the call, and an attach that states none says so —
returned in the route's response and logged — while seeding nothing, because
widening a channel on a caller's silence is the worse of the two failures.
Measured case: chat 95's cast reached the story with no recognition answer at
all, `known` stayed empty for nine turns, the player's own commanding officer
was composed as "a figure, backlit, indistinct, the face unreadable", and the
damage outlived the repair — turn 11 fed the character stage "I saw an
indistinct figure return to the science station console" as remembered_past
after `known` had filled. Recognition seeded late does not rewrite the memories
written before it.

**CAST-TO-CAST RECOGNITION NOW HAS AN AUTHORING SURFACE (2026-08-29).**
`already_known_cast` on the attach route closes the arriving member against
every other active cast member, through the same `seed_mutual_recognition`
call that carries the player answer, and the story-builder asks it once for
the group ("these characters already know each other"). The two answers stay
independent in both directions — a stranger to the player may arrive with the
crew she serves in — and an unanswered cast question is reported the same way
an unanswered player question is, but only when somebody is already here to be
a stranger to: the first arrival has nobody to know.

What it cost while it was missing, measured on chat 98's forty turns: `known`
held Picard → [player, Data], Data → [player, Worf], Worf → [player, Data].
Three senior officers of one watch, each missing a colleague. The asymmetry is
NOT a one-directional write — it is the correct signature of the only in-play
channel, hearing a name said aloud, and of the fact that the officer who did
most of the naming learned nothing from his own mouth. His composed view called
the man at tactical "the tall heavily built klingon male" on every one of those
turns while his own dialogue said "Mr. Worf" five times: a name from outside the
ledger, promoted into the objective record, because the engine had no way to be
told what the story took for granted.

WHAT REMAINS OPEN, and it is the owner's:

  * **WHAT THE DEFAULT SHOULD BE.** Deliberately not chosen here. A strangers-
    meeting attach is a real and valuable opening and the firewall is why;
    "the caller omitted a key" is not an authored answer to that question, and
    the engine could not previously tell the two apart. It can now, and warns
    rather than picks. Whether an attach should be REFUSED without an answer,
    and how loud a per-attach notice is in a UI, are the owner's to say.

<a id="unbuilt-1-96"></a>

### 1.96 One body, two simulations, and a door that only opens one way

The architecture the engine's owner names: **background life is the on-screen
half of the Charter**, and a body that walks off screen should carry what it
experienced back into ledgers the Charter can read. One continuous body, two
regimes — cheap statistical simulation while nobody is looking, beat-level
reaction while they are — with translation at the boundary.

**Half of it is built.** Charter to background is wired: `agents/background.py`
reads `background_presence_records` (:323), `presence_view` (:1131) and
`with_charter_presences` (:398), so a Charter body can appear in a scene and be
voiced with its own institutional context.

**The return path does not exist.** Grepping `persist/` and `agents/` for any
write to `state["minds"]` or any call to `hear_claim` returns nothing. Whatever
a Charter body sees, is told, or does on screen reaches no Charter ledger.

AND THE DOOR WAS BUILT FOR THIS TRAFFIC. `world/charter_mind.hear_claim`:

    THE ONLY UPTAKE DOOR. `hear` routes through it for body-to-body talk; an
    authored telling -- a voiced presence, the player, a major character
    speaking to a background body -- lands through the same door with the same
    rules: thinned by retention, scaled by the listener's regard for the
    teller, refused below the floor, and never overwriting a stronger holding.

It names the player and a major character speaking to a background body as its
own cases. Nothing in a played turn calls it.

WHAT THE MISSING HALF COSTS:

  * A Charter body appears, is voiced, is told something by the player, and
    walks away unchanged. Its head still holds only the presim's 692 hours.
  * Nothing accrues, so nothing distinguishes this presence from any other next
    time -- which is a mechanism behind the measured name churn (1.84a): four
    background names across fourteen beats, because there is no accumulating
    thing for a name to belong to.
  * The Charter's own upkeeps, watches and `stood`/`travelled` cannot reflect a
    shift a body actually spent on screen, so on-screen time is invisible to
    the institution that owns the body.

WHAT A TRANSLATION HAS TO PRESERVE, and this is the whole difficulty:

  1. **A CLAIM IS A BELIEF, NOT A FACT.** `hear_claim` already thins by
     retention, scales by regard for the teller, and refuses below a floor. An
     on-screen telling must arrive under those same rules, or the return path
     becomes a way to write certainties into heads that body-to-body talk could
     never produce.
  2. **THE CHARTER IS ALREADY THE CHEAP PERSISTENT MIND — that is its job.**
     An earlier revision of this entry warned that writing beliefs into a
     Charter body risked promoting somebody by accident. That was wrong, and
     wrong in the direction that would make this built too timidly.

     The Charter EXISTS to give bodies persistent belief and psychology
     cheaply. `state.minds` already holds ~14 claims per head across 42 heads,
     each with a decaying `strength`, an `as_of_hours`, and a `heard_from` --
     that is an inner life, persisted, and none of those bodies is a character.
     So an on-screen encounter updating a body's beliefs is the system working
     as designed, not a boundary being crossed.

     THE PROMOTION LINE IS COST AND CADENCE, NOT INNER STATE. A registered
     character gets a per-beat agent call carrying memory, appraisal,
     relationships and psychology. A Charter body gets beliefs that persist and
     decay with no model call at all. What promotion buys is the CALL, not the
     having of a mind. A translation should therefore write freely into the
     cheap mind and must not start spending a character's budget on a body that
     has not been promoted -- the thing to watch is per-beat cost, not richness.

  3. **THE FIREWALL RUNS BOTH WAYS.** A body must not carry off screen anything
     it had no channel to on screen, and must not bring on screen anything its
     Charter head holds at a strength the scene has not earned.

Not designed here. The observation is the owner's; the measurement is that one
direction is wired, the other is absent, and the door the other direction needs
already documents this exact traffic as its own use case.

<a id="unbuilt-1-96a"></a>

### 1.96a The stateless rule was written for one population and applied to two

`CLAUDE.md:101` states, as a property of the STAGE:

    `agents/background.py` gives named, unregistered background presences a
    stateless reaction per beat -- no persistent memory or psychology (that
    requires promotion to a real character).

The stage voices TWO populations and the sentence is true of only one:

  * **Tracked presences** -- names harvested from the Director's own prose into
    the `background_presences` world key by `track_background_presences`. These
    genuinely have no persistent inner state, and the rule describes them
    correctly.
  * **Charter bodies** -- reached through `background_presence_records`
    (`agents/background.py:323`) and `presence_view` (:1131). These carry
    `state.minds`: ~14 claims per head across 42 heads, each with a decaying
    `strength`, an `as_of_hours` and a `heard_from`. The Charter EXISTS to give
    them persistent belief cheaply. The rule is false of them by design.

WHY THIS MATTERS BEYOND TIDINESS. A doc that says the stage is stateless is a
doc that says the return path in 1.96 should not exist -- there is no reason to
translate an on-screen encounter back into a ledger if the presence has no
ledger. **The architecture was closed off by a description rather than by a
decision.** The engine's owner's stated intent is the opposite: the Charter is
the cheap persistent mind, and that is its job.

The correction is not to delete the sentence -- it is right about tracked
presences, and the promotion boundary it names is real. It is to say which
population it governs, and to state the other case beside it: a Charter body
voiced through this stage brings a persisted mind with it and may carry one away.

<a id="unbuilt-1-97"></a>

### 1.97 Volition reads history; the rest of the social physics does not

Landed 2026-08-27. `charter_practice._state_of` built
`{bodies, figures, minds, needs, regard, blame, at}`, so a Charter body
deciding what to do could not see anything that had ever passed between it
and the person in front of it. It now carries four holder-owned stores —
`experiences`, `served_beside`, `judgments`, `commitments` — and `_between`
derives a per-pair digest (`familiar`, `affect`, `debt`, `owed`) that the six
affordance builders weight utility on. Design 1 of
[`docs/guides/RESEARCH.md`](guides/RESEARCH.md) §1.7.6. No new persisted
state: the digest is derived per window and discarded. Measured on
`big_ship(crew=40)`, 480 h onscreen, seed 3, against the identical run with
the stores withheld — 86 `(actor, act, other)` triples moved and the mean
`served_beside` count of the body a question was taken to rose 63.8 → 71.3.
What that leaves open:

- **All five of §1.7.6 landed 2026-08-27** and each has its own entry —
  §1.97 (this one), §1.98, §1.99, §1.99a, §1.99b — including what they did
  NOT close: `harm_done` still has no producer at all, and a HEALTHY
  institution's judgment network is still empty on purpose, which is the half
  of design 2's stated gap that remains open and which leaves designs 1 and 3
  wired and inert in a well-run institution.
- **The `affect` axis is still thin in HEALTH, and half of that is now
  answered.** `charter_run._record_social_experiences` stamps no
  `valence`/`arousal` — only `_record_coarse_experiences`' `felt()` does — so
  the row half of the axis is fed by `encounter`/`acquaintance` rows alone.
  The `judgments` half arrived with design 2: measured on the famine arm of
  `twin_towns(40)` over a simulated quarter, judgment holders went 6 → 40
  and stances 29 → 149. On the HEALTHY arm both halves are still zero, and
  §1.98 argues that is the design rather than a gap. **Do not compensate by
  raising `HISTORY_WEIGHT`**; that would make the constant mean something
  different once the evidence arrives.
- **`STALE_HOURS` was designed, measured and not built.** The proposed sixth
  term ("we have not spoken in a while" as a reason to tell) was dropped on
  measurement, and the measurement is not the one that was predicted. The
  prediction was that `stale` would saturate offscreen and carry no
  information; measured over 9,024 digest reads on the 40-body fixture it
  discriminates well onscreen (gap median 16 h, p90 96 h, only 14.9 %
  saturated at a 72 h constant). It was dropped for two other reasons. First,
  it attaches to `tell`, and `tell` fired **zero** times in 480 onscreen
  hours on `big_ship(40)` and on `twin_towns(60)` alike — a constant that
  moves nothing in either of the repo's own large fixtures cannot be set from
  evidence. Second, it breaks the subtraction guard: a pair with no rows at
  all has no last hour, so the term must read either 0.0 ("we just spoke",
  false) or 1.0 (which makes a total stranger the most tellable body in the
  room). Neither default is neutral, and a term with no neutral is not
  additive. Revisit if and when `tell` is observed firing.
- **`_afford_tend` reads `state["needs"][other]` and names the other's worst
  need key in its own `line`.** Pre-existing and untouched by design 1, but
  it is the nearest thing to a live leak in the module: being on the floor is
  visible from across a room, and *which* need put you there is interior.
  The affordance would still work off the visible fact alone.
- **~~`_afford_accuse` reads `state["blame"][other]`~~ — CLOSED 2026-08-27,
  and it had to be, because the same day made it reachable.** The register
  read was dead code when this bullet was written: `quarrel` had no opener
  but `_afford_accuse`'s own effect, and zero `accuse` acts were measured on
  screen and off, in health and in famine. Design 2's `opportunities` opener
  and design 5's shipped default rule then gave it two live openers, one
  onscreen and one everywhere — so the institution's private register was
  selecting who an ordinary body rounded on, and `0.55 + 0.1 × blame_count`
  was handing a monotone reading of the counter's MAGNITUDE to a scene-manager
  model through `charter_runtime.presence_view`'s `action_instances`. A leak
  nobody can reach is a residual; a leak on the default path is a defect.
  `charter_practice.grievance_against` is the channel that was missing: the
  actor's OWN claims, in two shapes — one that names `other` as the party at
  fault (`GRIEVANCE_KINDS`), and one that this place has failed while `other`
  is standing in it (`PLACE_FAILURE_KINDS`). Both `_afford_accuse` and the
  `opportunities` opener gate on it and neither reads `blame` any more, and
  the utility is sized on the actor's own count. `politics.blame` still
  decides which of its own situations the INSTITUTION has cause to open (the
  opener's outer loop, and design 5's `blame_landed` rule), which is
  bookkeeping rather than conduct — nothing opens between two people who have
  no reason of their own.
  **Measured before and after on the same tree** (the "before" arm is the same
  working tree with these three edits reverted, so nothing else differs), on
  `twin_towns(40)` driven into famine for a simulated quarter, window 4.0,
  seed 7:

  | | register gate | channel gate |
  | --- | --- | --- |
  | accusations, on screen | 64 | 58 |
  | bodies ever told they were blamed | 2 | 7 |
  | largest judgment axis anywhere | 0.2062 | 0.3553 |
  | axes at or above `TIE_FORM` (0.30) | 0 of 600 | 2 of 520 |
  | signed ties formed | 0 | **2** |
  | accusations, off screen | 2 | 2 |

  The accusation now follows perception rather than the books, so a body the
  register never blamed can be rounded on by somebody who watched the road
  fail beside them, and the blamed body rounds back on its accusers: 7 people
  are told rather than the 2 the books name, and the institution being WRONG
  about who is answerable is visible as that divergence instead of being
  laundered into an accuser's mouth. It also LAPSES — a claim is deleted once
  it fades below `charter_mind.PERSONAL_FLOOR`, where the register is monotone
  and would still be a reason a decade later. And it is the first thing in
  this branch to push an axis past `TIE_FORM` from ordinary simulation: the
  two signed ties in the right-hand column are the only ones any arm of
  §1.7.6 has produced without a hand-planted store.
- **The accuser still has no channel to WHO WAS POSTED where.** The place
  shape above requires the pair to be standing in the failed place, which is
  where a still-posted body is; a body that has walked away is unaccusable
  even though the institution blames it, because nothing a bystander can
  perceive links a person to an upkeep they are no longer at. Measured on
  `twin_towns(240)` driven into famine for a simulated month off screen: the
  blamed pair had moved to `low_0` by the window the consequence rule fired,
  and 0 bodies were told — **in BOTH arms**, so this costs nothing today, and
  §1.99b's "0 → 2 told" for that fixture does not reproduce on the finished
  tree under either gate. The honest fix is a perceivable post↔body link —
  `post_filled_again` is already WITNESSABLE and names the body — and it needs
  `posts` inside `_state_of`, which is a widening this change did not license.
- **The memo assumes the four stores do not move under a `state` dict.**
  True today — `enact` writes `minds`, `needs` and `regard` only. An
  affordance that minted an experience row inside its own effect would
  silently serve a stale digest for the rest of the window. Stated as an
  invariant in the module docstring; nothing enforces it.

<a id="unbuilt-1-98"></a>

### 1.98 Ordinary evidence, and the healthy institution that is still empty

Landed 2026-08-27. Design 2 of
[`docs/guides/RESEARCH.md`](guides/RESEARCH.md) §1.7.6. The five-axis
judgment network measured EMPTY across four charters of a real story and
across a simulated YEAR of `tests/charter_worlds.twin_towns(40)` — 0 events
and 0 judgment holders, while that same year deposited 6,742 experience rows.
The people were living and none of it was evidence.

What landed: `charter_news.check_reports` (a body standing where a
second-hand rumour named settles it against the place and judges the teller —
`report_confirmed`/`report_refuted`, which had weights, a `WITNESSABLE` entry
and runtime phrasing and no producer anywhere); `accusation` and `apology`
minted from the `accuse` and `reconcile` acts, plus the `quarrel` opener that
made those acts reachable at all; `institution_order_executed` spelled the way
the event is spelled; `toward` carried through `news_claim`; and diminishing
returns on the judgment update. Measured on `twin_towns(40)`, window 4.0, seed
7, before → after: healthy year off screen 0 → 0 events, 0 → 0 judgment
holders; famine quarter off screen 6 → 40 holders and 29 → 149 stances, 130
surviving `reasons` citations naming `report_confirmed`, and no axis above
0.999994 against 63 of 145 axes sitting at exactly 1.000 before; famine quarter on screen 0 → 14 accusations and 27 checks. Coarse cost,
best-of-3 interleaved on the healthy year: 1.953 → 1.979 ms/simulated hour.

What that leaves open:

- **A HEALTHY institution's judgment network is still empty, and this entry
  claims that is the design.** None of the three producers fires in a
  well-run institution: there are no rumours to check because there are no
  events to be second-hand about, and nobody is blamed because nothing
  failed. If the intent behind design 2 was a non-empty healthy network then
  this does not deliver it, and the two honest routes remain what they were:
  a new signal kind for ordinary exchange — the strongest candidate is
  `post_filled_again`, already witnessable and carrying no `body` field, so
  "somebody turned up" cannot be evidence about the person who turned up —
  or moving familiarity into judgments, which
  `persist/commit_background.py:2271-2288` argues against because
  `served_beside` already has its own store and its own promotion path.
- **`harm_done` still has no producer at all.** Declared witnessable, given
  the heaviest negative weights in `DEFAULT_SIGNALS` (trust −0.13, fear
  +0.10, suspicion +0.08), phrased in two places, and emitted by nothing.
  There is no act in `charter_practice._AFFORDANCES` that harms anybody, so
  unlike `accusation` this is not a wiring gap: the practice does not exist.
- **`reconcile` fired ZERO times, so `apology` has a producer that has never
  been observed producing.** Measured over a simulated quarter of
  `twin_towns(40)` on screen in famine: 7,769 `ask`, 527 `greet`, 14
  `accuse`, 1 `tell`, 0 `reconcile`, 0 `tend`. `_afford_reconcile` returns
  0.4 and `_afford_ask` returns 0.35 + 0.3·(1 − what the listener already
  holds), so an actor with any converse practice open outbids making peace,
  and the quarrel then dies of `IDLE_CLOSE_HOURS` instead. The producer is
  right; whether a quarrel can ever END in this population is not proven.
  Pinned by unit test, not by observation.
- **A refuted teller may have been telling the truth when they told it.**
  A claim that was true when spoken and stale by the time somebody stood at
  the place is refuted exactly like a lie, which is systematic injustice and
  erodes trust for everybody. Not observed as a problem — the famine arm
  measured 130 `report_confirmed` citations and no refutations reaching a
  stance — but nothing bounds it. If a confirm:refute ratio below 1.0 is ever
  measured in a healthy-then-broken arm, the fix is a freshness bound on the
  claim's `as_of_hours`, and the comment should say that beyond it a stale
  claim is the world changing rather than the teller lying.
- **A check-claim is a news claim, so `charter_talk.tellable` may select it
  and it will spread.** A listener then forms a judgment about the teller at
  `hearsay_weight` — which is `normalize_social_norms`' `hearsay_weight`
  finally carrying something, and legitimate speech. It is also a behaviour
  nobody has watched yet, and the spread should be measured before it is
  called a feature.
- **`news_key` stamps the hour and derives its subject from a fixed field
  chain, so two acts by the same actor in the same window collide into one
  claim.** `enact` gives each body exactly one act per beat, so this cannot
  happen today and will start happening the day that changes. The same
  exposure sits at `charter_runtime._scheduled_row`, which uses
  `INSERT OR IGNORE` on `(kind, subject, at_hours)`.

<a id="unbuilt-1-99"></a>

### 1.99 The discrete tie, and the health that only ever earns one label

Landed 2026-08-27. Design 3 of
[`docs/guides/RESEARCH.md`](guides/RESEARCH.md) §1.7.6. Charter had a
directional five-axis judgment network and no word for what it said, so
nothing downstream — a narrator, a scene ledger, a promoted character's
relationship graph — could state a relationship plainly. `world/charter_social`
now derives six labels (`close`, `at_odds`, `wary`, `afraid_of`,
`looks_up_to`, `familiar`) from state that already existed: the holder's own
stance, its own directed regard, and its own `served_beside` count. Stored
sparsely as the charter's `ties`, formed off dirty sets `charter_run.step` and
`charter_observe.apply_public_evidence` already compute, surfaced inside
`scene_ledger`'s existing `knows_here` block and on `promotion_handoff`'s
existing `acquaintances` rows — no new key on either payload, so the presence
allowlist at `tests/test_charter_runtime.py` did not widen.

Measured on `tests/charter_worlds.twin_towns(40)`. Window 8 h, seed 5,
healthy: `familiar` labels 0.0 % of 1560 directed pairs after a simulated
week, 14.7 % after a month, 26.4 % after a year against a 27.9 % ceiling of
pairs that ever shared a place — which is what set `FAMILIAR_FLOOR = 24`
shared windows. Window 4 h, seed 7, driven into famine: 40 judgment holders,
149 stances, 16 `close` and 11 `looks_up_to` labels across the quarter, 11 of
them requited. Coarse cost, the tie pass swapped for a no-op and the two arms
strictly INTERLEAVED on `.venv` so drift cannot land on one of them: healthy
simulated year 17.40/16.87 s with the pass against 17.49/16.82 s without —
inside the run-to-run spread, and one of the tie arms came out faster, which is
what noise looks like. Famine quarter 24.47/25.69 s against 24.05/23.38 s,
about 3 %, and that is the whole of the pass's cost: it is paid only where 40
bodies actually hold stances. The holder gate is why — a body holding neither
a judgment nor a tie is skipped before its co-presence is walked, so a healthy
institution pays O(bodies) per window and not O(pairs).

What that leaves open:

- **A HEALTHY institution produces `familiar` AND NOTHING ELSE, measured, and
  this entry claims that is §1.98's gap re-measured rather than a defect in
  this layer.** A simulated year of `twin_towns(40)` at window 8 h holds 4
  judgment holders, 7 stances and ZERO signed labels; the signed half only
  fires once something goes wrong, because that is the only circumstance in
  which the evidence layer under it fills. Pinned by
  `test_a_healthy_year_of_this_engine_forms_no_signed_tie`, which is written
  to FAIL the day §1.98's first bullet is closed. **Do not close it by
  lowering `TIE_FORM` until `familiar` pairs start reading as friends** —
  that is precisely the tie-that-contradicts-the-numbers failure the
  validator exists to prevent. The threshold is re-set from the new
  distribution or it is not re-set.
- **`TIE_FORM = 0.30` is derived from `DEFAULT_SIGNALS`' per-event magnitudes
  (0.02–0.18) and not from an observed distribution.** It says "about five
  ordinary acts in one direction, or two grave ones", which is defensible and
  is still a prediction. The famine arm now gives it something to bite on;
  nothing has measured what an ORDINARY year's distribution looks like,
  because there is not one yet.
- **The incremental updater's completeness rests on three properties nothing
  enforces.** `served_beside` only rises, judgments never decay, and
  `TIE_WEIGHTS["regard"] = 0.15` is below every form threshold. The third is
  guarded by `test_regard_alone_cannot_form_a_tie`; the first two are stated
  at the `update_ties` call site and in its docstring and are otherwise
  properties of today's code. A judgment-decay feature landing later makes
  unvisited pairs genuinely stale, and this walk then has to become a full
  sweep or gain a decay-driven dirty set of its own.
- **A body wrongly blamed can lose a tie it should keep.** `attribute_blame`
  costs 0.15 of everyone else's regard per incident, the validator deletes a
  contradicted label instantly and with no dwell, and blame is an
  INSTITUTIONAL conclusion that may be exactly wrong (`charter_politics.py`
  says so in its own docstring). The bound is regard's 0.15 weight: it can
  push a bond by that much and no more, and it can never form one. If that
  weight is ever raised this becomes a real defect rather than a bounded one.
- **The lorebook owns what a tie is CALLED in this world, and nothing wires
  that up.** `knows_here` now carries a short English word into a model
  payload for every presence in a scene, and `scene_ledger`'s own docstring
  is the warning: a payload large enough to restate gets restated. One capped
  token per already-capped entry is small, but `close` is a word a model will
  say aloud verbatim, and no prompt-side vocabulary hook exists.
- **The label does not cross promotion into the character tier.** It rides
  `promotion_handoff`'s `acquaintances` rows as `tie`/`tie_since_hours` and
  `persist/commit_background.py`'s acquaintance-edge writer drops it on the
  floor, because `mind/memory_relationships.Relationship` has no `tie` field.
  Adding one is the full `docs/guides/DATABASE.md` new-persistent-field
  checklist — the graph is a persisted world-key blob crossing archive,
  checkpoint and branch paths — and was deliberately left out of the charter
  change.
- **`test_ties_do_not_grow_with_time` was planned as a decade against a year
  and is not built in that shape.** On today's engine a healthy decade and a
  healthy year both hold ZERO signed rows, so the comparison proves nothing,
  and the run costs 90–110 s. The bound is asserted directly instead — rows
  are capped per holder at `TIE_CAP` and a window in which nothing moved
  rewrites nothing (`test_ties_are_capped_per_holder_however_long_the_run`,
  `test_a_quiet_window_writes_no_tie_row`). What is NOT asserted is the
  behaviour under a long CATASTROPHE: a famine arm's rows go 9 → 16 → 27 as
  480 h becomes 1920 h, which tracks the events (292 → 1763) rather than the
  clock, and is bounded by bodies × `TIE_CAP`, but nobody has run it to the
  cap.

<a id="unbuilt-1-99a"></a>

### 1.99a Status as a temporary trait, and the accusation nobody offscreen makes

Landed 2026-08-27. Design 4 of
[`docs/guides/RESEARCH.md`](guides/RESEARCH.md) §1.7.6. Charter had permanent
traits (`charter_temper`), needs, felt state and a service tally, and nothing
socially TEMPORARY — no newly raised, no lately helped, no accused to your
face, no in disgrace. `world/charter_mark.py` is four marks with four
lifetimes over one new charter key, `marks`, normalized in
`charter_model.normalize_charter` and filtered to live bodies there exactly as
`experiences` and `habit_runs` are. One row per (body, kind): a re-trigger
overwrites `since` rather than appending, and every row is pruned at expiry —
so the store is bounded by bodies × 4 and a simulated year of a healthy
institution ends holding NOTHING.

THE FIREWALL SPLIT IS THE DESIGN'S SPINE and it is an allowlist,
`BODY_MARKS`, for the same reason `charter_news.WITNESSABLE` is one.
`posted`, `aided` and `accused` each have an origin the marked body was
present for — it was handed the duty, somebody tended it in the room,
somebody said it to its face — and they reach `charter_feel.appraise_window`
and `scene_ledger`'s presence slice. `disgraced` is the register's own:
`attribute_blame` follows the watch the charter BELIEVED it had arranged, so a
body can be disgraced for a post it was never at, and it reaches exactly the
planner's reluctance axis and `charter_log.life_of`, which is author
diagnostics no mind receives. Measured from both ends by
`test_being_told_to_your_face_is_felt_and_the_ledger_alone_is_not`: identical
register blame leaves the blamed body at strain 0.163 / load 0.067 with
somebody saying it aloud and at strain 0.0 / load 0.0 without.

Measured on `.venv`, this workstation. `big_town(40)`, healthy simulated year,
window 4.0, seed 3: 13 of 40 bodies ever `posted`, 0.31 % of (body, window)
pairs holding it, and the store EMPTY at the end of the year. Cost, the
mark writer swapped for a no-op and the two arms strictly INTERLEAVED in one
process so drift cannot land on one of them: 23.64/23.67 s live against
22.71/23.16 s inert, +2.2 % to +4.1 % depending on which pair, against the
5 % gate this package uses. The layer is one dict pass over the bodies per
window and nothing quadratic. The same fixture with needs
seeded: 804 `aid_given` acts over the year, 6 bodies ever `aided`, 12.39 %
mean held. `twin_towns(240)` driven into famine for a simulated month: 48 of
240 ever `posted`, 2 ever `disgraced`, 0 `accused`. `twin_towns(40)` famine
quarter, before → after: 2013 → 1567 events and 658 → 524 `body_unable`,
because being tended now proposes pleasure and a positive-only window no
longer manufactures strain (see below).

`DISGRACE_RELUCTANCE = 0.6` was set against `pressure`, not against a
sweep — the planner's first sort component is
`criticality + standing + pressure + disgrace`, so the number is the
exhaustion at which the institution stops preferring a clean hand. Measured on
a two-body works fixture: at 0.3 the disgraced hand is back on the bill once
the clean one reaches need level 0.6; at 0.9 the institution never reaches for
it at all and works the clean hand down to 0.2. Below 1.0 on purpose, because
`criticality` contributes whole numbers to the same component and a disgrace
must never outweigh being the last body qualified for another post.

What that leaves open:

- ~~**`accused` has no OFFSCREEN producer, and the measurement says so.**~~
  **CLOSED 2026-08-27 by design 5** (§1.99b). It was true as written:
  `quarrel` is not in `COARSE_PRACTICES`, so an institution nobody was looking
  at produced zero accusations in health and in famine (`twin_towns(240)`,
  famine month: 0). `charter_trigger`'s one shipped default rule,
  `blame_opens_a_quarrel`, opens the situation from the blame LANDING rather
  than from the ledger, and the trigger pass runs in both branches of `step` —
  so the same fixture now reaches `heard_blame` and mints `accused` off
  screen. The entry is kept struck through rather than deleted because the
  reasoning ("an accusation IS a scene") was the argument for leaving it, and
  it was wrong for the offscreen case specifically: a blame that lands where
  nobody is looking still lands on a person.
- **A mark minted by `charter_author.authored` is never APPRAISED.** The
  author path folds the onset into the store correctly and the presence slice
  and the planner both read it, but `advance_feel` runs only inside `step` and
  sees only that window's `fresh` list — and an authored mark stamped at
  `clock_hours` is indistinguishable from one the previous window minted at
  the same hour, so it cannot be recovered as fresh later. The clean fix is
  for `authored` to appraise the body it acted on, which is a larger change to
  a module that deliberately advances no time; the alternative, a per-row
  "appraised" flag, is the state growth this design exists to avoid. So a
  figure's accusation is currently seen and scored and not felt.
- **`posted` peaks at the institution's first window and that is honest, not
  a bug.** 32.5 % of `big_town(40)` holds it at hour 4, because the whole bill
  is handed out at once and everybody genuinely is newly raised. Any longer
  lifetime, or a churnier bill, pushes the standing fraction toward everybody
  — and a mark most of the institution holds is not a mark. The held fraction
  is the number to re-measure if `MARK_HOURS["posted"]` is ever raised; do not
  infer it from the lifetime.
- **`mood_weight` double-counts blame with the disgrace term.**
  `charter_needs.mood` already takes `blamed` as an input and joins the same
  reluctance axis, so an arm that raises `mood_weight` above its shipped 0.0
  pays for a fresh failure twice. Stated at the call site; nothing changes at
  the default.
- **`marks` is deliberately absent from `promotion_handoff`.** The character
  tier has no reader for a Charter-window scoring bias, so carrying one would
  be dead weight. `charter_runtime.bind_promoted_character` purges the store
  along with minds/needs/feel/heard_blame, and that purge is guarded by
  exactly one test.

<a id="unbuilt-1-99b"></a>

### 1.99b Trigger rules, and the blame that finally reaches somebody

Landed 2026-08-27. Design 5 of
[`docs/guides/RESEARCH.md`](guides/RESEARCH.md) §1.7.6, the last of the five,
and the one whose whole risk was that a cascade does not stop. Charter had no
way for a state change to have a consequence: an act changed state and nothing
fired off the change, so the social layer only moved when the planner or an
author prodded it. `world/charter_trigger.py` is authored rules that read one
objective CHANGE and produce one objective consequence — open a practice, set
a `charter_mark`, emit a witnessable event.

THE PASS READS A CHANGE AND NEVER A STATE, which is what makes it free rather
than merely cheap. A window deposits a capped `pending_changes` frame and the
next one fires on it; with an empty frame `fire_triggers` returns on one falsy
test. Three new charter keys, all normalized in
`charter_model.normalize_charter` because that runs at the head of every
`step`: `triggers` (merged over `DEFAULT_TRIGGERS` by id), `pending_changes`
(`PENDING_CHANGE_CAP = 32`, round-robin across the three families) and
`trigger_last` (pruned to the longest refractory, `TRIGGER_MEMORY_CAP = 256`).

THE FIREWALL IS HELD BY THE SIGNATURE, not by a docstring. `fire_triggers` is
handed change rows and a body index and nothing else; the module imports none
of `charter_mind`, `charter_social`, `charter_feel`, `charter_needs`,
`charter_talk`, `charter_observe`, `charter_politics` or `charter_model`, and
`test_the_pass_is_not_given_a_head_to_read` pins both ends. `TRIGGER_EMITTABLE`
is a TIGHTER allowlist than `charter_news.WITNESSABLE` — only `aid_given` and
`harm_done`, whose truth condition is exactly "this visibly happened between
these people here" — because minting an `institution_order_executed` or a
`report_confirmed` from a rule would put a false institutional fact into every
head in the room at full first-hand strength with a stable news key two
witnesses would agree on. There is no `set_judgment` op: a rule that wants to
move an opinion emits an event, `witness` decides who was present, and the
axis moves next window with an evidence id its holder can cite.

THE `on` SIDE WAS OPEN AND IS NOW ALLOWLISTED TOO (`perceivable_change`,
2026-08-27). Which kinds a rule may MINT was closed from the day this shipped;
which changes it may mint them FROM was not, so the same hole stayed reachable
from the other end. Both of these normalized clean and fired on `.venv`:
`{"on": "blame_landed", "then": [{"op": "emit", "kind": "harm_done", …}]}`
put a first-hand claim into every head in the room off a move of the
institution's private counter, and `DEFAULT_SIGNALS["harm_done"]` then moved
trust −0.13 / fear +0.10 / suspicion +0.08 in each of them, citing evidence no
witness could have seen; `{"on": "event:post_unfilled", "then": [{"op":
"set_mark", "mark": "accused", …}]}` left a body feeling it at
`charter_feel`'s −0.6 and showing it in the presence slice with nothing said
aloud, no accuser and `heard_blame` still empty. An `act:` change passes
unconditionally (an act happens in front of whoever is standing there) and an
`event:` change passes only where `charter_news.WITNESSABLE` says a body could
have seen it — read from that module rather than copied, so a kind admitted
there tomorrow is admitted here the same day. `open_practice` is deliberately
NOT held to this: opening a situation puts nothing in anybody's head, and
every affordance inside one applies its own channel gate at act time.
`disgraced` is likewise unaffected, because it is the register's own mark
wherever it comes from.

WHAT IT ACTUALLY BOUGHT, measured on `.venv`, this workstation. The one
shipped default rule, `blame_opens_a_quarrel`, closes the residual §1.99a
registered: a blame landing OFF SCREEN reached nobody, because `quarrel` is
not in `COARSE_PRACTICES` and the offscreen branch passes no ledger. On the
four-body yard fixture the whole chain now runs in two windows — blame lands
at hour 20 and marks the keeper `disgraced`; the trigger fires at hour 24,
opens the quarrel, somebody accuses her in the same window, `heard_blame`
becomes non-empty and she carries `accused` with the accuser named in `by`.
`twin_towns(240)` driven into famine for a simulated month went from 0 bodies
ever told they were blamed to 2; `twin_towns(40)` over a famine quarter, 0 to
1. A healthy simulated year of `big_town(40)` still fires NOTHING, which is
the point.

**Those two fixture numbers do not reproduce on the finished tree**, and the
honest reading is that they were measured mid-branch. Re-measured 2026-08-27
with all five designs in and the accusation channel of §1.97 landed:
`twin_towns(240)` famine month off screen tells 0 bodies whether the gate is
the register or the channel — the blamed pair have moved off the failed place
by the window the rule fires — and `twin_towns(40)` famine quarter off screen
tells 2 in both arms. What the rule demonstrably still does is the yard
fixture's two-window chain below, which is a placement proof rather than a
population measurement.

COST. `big_town(40)` at 4,380 hours, window 4.0, seed 3, with
`fire_triggers`/`changes_from` swapped for no-ops and three pairs of arms
strictly INTERLEAVED in one process (the §1.99 lesson about arms measured
minutes apart): 10.71/10.27/10.23 s live against 10.15/10.53/10.17 s inert —
+5.5 %, −2.4 %, +0.6 %, mean +1.2 %, so the pass is not visible above
run-to-run noise. Micro-profiled it is 18 µs per window, of which
`normalize_triggers` is 15, which is 0.2 % of the window. Determinism: two
runs of seed 11 over 400 hours agree byte-for-byte on `fired`, `marks`,
`practices`, `trigger_last` and `heard_blame`, and a JSON round trip through
`normalize_charter` is a fixed point on all three new keys.

THE CONSTANTS, and what set them:

- `TRIGGER_DEPTH = 2`. Measured with one deliberately self-feeding authored
  rule (`on: event:harm_done → emit harm_done`, one authored `harm_done`
  seeded) over 2,000 simulated hours of SHIP: the rule produces exactly 1, 2,
  3 and 4 consequences at depth 1, 2, 3 and 4, and the quiet control emits
  zero at every one — so this bound is the only thing stopping it, which is
  what a bound should be.
- `TRIGGER_YIELD_CAP = 8`. Per-window consequence count with the shipped
  defaults: 0 in total over a simulated year of `big_town(40)` (2,190
  windows); 3 in total, maximum 2, over a famine month of `twin_towns(240)`;
  2 in total, maximum 1, over a famine quarter of `twin_towns(40)`. p99 is 0
  on all three. It never binds in play and always binds on a rulebase that
  has gone wrong.
- `PENDING_CHANGE_CAP = 32`. The busiest window measured produced 184 raw
  changes (famine week, `twin_towns(240)`), mean 38.7; `twin_towns(40)` over a
  famine quarter averages 5.0.

FOUR DEVIATIONS from the plan this was built to, each because the code or a
measurement said so:

1. **No `statuses` key was built, and `set_mark` writes into `marks`
   instead.** The plan predicted design 4 might slip and left `statuses` with
   no behavioural reader. Design 4 landed first, and `charter_mark` already
   holds socially temporary facts with a lifetime per kind, an expiry prune, a
   body-scope allowlist and three readers. A second store of the same idea can
   only ever disagree with the first — the argument §1.99's tie layer makes
   about labels and numbers. So `set_mark`'s vocabulary is `charter_mark.MARKS`
   and nothing else: a row whose kind has no lifetime could never expire, so
   it would be a permanent trait wearing the word "temporary".
2. **The plan's second default rule, `aid_leaves_a_body_in_credit`, was not
   built.** Design 4 mints `aided` directly in `charter_run` from
   `act == "tend"`, in both branches. A trigger re-minting it a window later
   would be a second writer of the same fact that can only disagree with the
   first. All four marks have direct producers, so `set_mark` ships with no
   default rule at all and is an author surface — which is honest, because
   unlike the plan's `statuses` a mark written there is read immediately.
3. **The plan's step 4 was already done.** It asked for `attribute_blame` to
   be hoisted out of the `after_charter` assembly so the blame delta could be
   computed where the event list is final, and warned that the reorder was a
   replay risk. Design 4 had already hoisted it and already computes the delta
   as `disgraced`. No reorder was made and `TestReplay` never moved.
4. **`fire_triggers` takes no `offscreen` parameter.** The plan passed
   `offscreen = not active` and gave it no job. The whole argument for the
   shipped default is that the offscreen branch is where `quarrel` has no
   opener, so gating on it would defeat the rule; an unread parameter is a
   smell this package does not need a second instance of.

What that leaves open:

- **`emit` ships with no default rule and `harm_done` still has no producer
  anywhere.** That is design 2's residual (§1.98) and is unchanged: a trigger
  produces consequences and `harm_done` is primary conduct, so minting one
  from a rule would be the engine inventing an assault nobody committed.
  `TRIGGER_EMITTABLE` carries it so an author CAN, which is the right split.
- **Depth is carried on minted EVENTS and not through an opened practice.** An
  `open_practice` consequence mints no change row, so it cannot cascade in
  principle; but a triggered `quarrel` can produce an `accuse` act, that act
  re-enters the frame as `act:accuse` at depth 0, and a rule firing on
  `act:accuse` would restart the count. Bounded in practice by the refractory,
  the yield cap and `_afford_accuse`'s own regard gate (roughly two
  accusations per pair), and stated here rather than hidden. The clean fix is
  for `enact` to return which practice each act was taken in, which is a
  change to a returned shape with several callers.
- **~~`_afford_accuse` reads the institution's private blame register~~ —
  CLOSED 2026-08-27.** Making that path live everywhere is what turned it from
  a residual into a defect, and §1.97 records the fix: an accusation now
  requires the accuser's own claim (`charter_practice.grievance_against`) and
  reads no register. The shipped rule still fires on `blame_landed`, which is
  the institution deciding to open one of its own situations — bookkeeping,
  not conduct — and the pair it opens between produces nothing unless one of
  them has a reason of their own.
- **`changes_from` mints a full row and formats a key for every act and event,
  then keeps 32.** Profiled on `big_town(1000)` over 18 windows: 6,417
  `_change` calls, 0.104 s cumulative under cProfile. Left alone deliberately —
  `_cap_changes` sorts by `(at_hours, key)` in BOTH branches, so the keys are
  needed for every row before the cap can pick, and capping earlier would
  change which rows survive, which is a determinism change with no measured
  benefit. The persisted field is correctly bounded either way; this is per-act
  work whose result is discarded on the busiest windows and nothing more.
- **A rule cannot fire on the AUTHOR path.** `charter_author.authored`
  advances no time and deposits no frame, so an authored act's consequences
  wait for the next `step`. Consistent with §1.99a's finding that an authored
  mark is never appraised, and open for the same reason: `authored`
  deliberately does not advance the world.

<a id="unbuilt-1-99c"></a>

### 1.99c The Charter scale audit's 45-second guard is broken, and the branch broke it

Found 2026-08-27 while measuring design 5; **re-measured 2026-08-27 after a
review found the baseline was 100 commits from the wrong side of the branch
point.** `tools/charter_audit_scale.py::test_a_simulated_month_costs_seconds_not_minutes`
asserts a simulated month of `big_ship(500)` costs under 45 s, and its own
comment records the measurement that set the bound: "below 30 s in isolation
and 30.4–33.2 s after several minutes of sustained test load".

The first version of this entry called 48cdd94 "committed HEAD, before any of
the §1.7.6 designs" and concluded the guard "was already failing by 2x at
HEAD". 48cdd94 is `main`'s tip, not this branch's baseline —
`git rev-list --count 48cdd94..96916f6` is 100 — and it PASSES. Measured on
`.venv`, this workstation, three trees strictly interleaved in one sitting,
three cycles, `big_ship(500)` at 720 h:

| tree | seconds |
| --- | --- |
| `main` at 48cdd94 | 43.04 / 42.31 / 41.81 |
| this branch's committed baseline, 96916f6 | 89.49 / 88.64 / 88.62 |
| the working tree, all five designs plus the review fixes | 90.02 / 91.03 / 91.96 |

Absolute seconds move a lot with what else is on the box — the same working
tree read 64.7 s under `pytest` on a quiet one — so the interleaved ratios are
the load-bearing part of the table and not the raw numbers. So the guard was
passing before this branch and is failing on it, by a little over 2x, and **the failure is almost entirely already committed**: the
uncommitted work adds 1.6 % on top of 96916f6, not the 21 % a review measured
before `charter_mark.held_marks` stopped normalizing the whole store (§1.97,
`_normalize_row`).

**And the cause is not the §1.7.6 work.** Bisected in one sitting on the same
fixture at 240 h, one rep per tree, the box otherwise quiet:

| tree | seconds | step |
| --- | --- | --- |
| 48cdd94 (`main`) | 8.70 | — |
| be82486 *A memory is how it landed, not that it happened* | 11.77 | +35 % over 96 commits |
| 3ac5d2c *All systems nominal is a report, not what happened to these people* | 15.60 | **+33 % over two commits** |
| b5bc630 | 15.78 | +1 % |
| 96916f6 (designs 1–2 and the tie layer) | 16.17 | +2.5 % |
| working tree (designs 3–5 finished, plus the review fixes) | 16.61 | +2.7 % |

3ac5d2c is the commit that made the offscreen branch stop being empty —
`COARSE_PRACTICES`, `_record_coarse_experiences`, the `ENCOUNTER_ODDS` draw —
and a third of the cost of a 500-hand month arrived with it. That is a
deliberate feature and its docstring argues for it; what nobody did was
re-measure the guard the same day. All five §1.7.6 designs together are about
5 % of the run.

**The assertion is deliberately left failing.** Raising it would erase the
evidence, and the audit is opt-in — `tools/` is outside `testpaths`, so it is
not collected by `pytest` and nothing in CI is red because of it. What needs
doing is a decision about 3ac5d2c's writers at 500 bodies, not a new constant.

<a id="unbuilt-1-99d"></a>

### 1.99d A person is owned by an institution, and a timeskip carries nobody

TWO OWNER DESIGNS RECORDED 2026-08-27, the second depending on the first.

**A Charter owns people, and it should only employ them.** One charter's state
holds roughly fifteen PERSON-scoped stores -- `bodies`, `minds`, `needs`,
`feel`, `experiences`, `served_beside`, `stood`, `judgments`, `ties`, `marks`,
`commitments`, `habit_runs`, `travelled`, `heard_blame`, `politics.regard` --
beside thirteen INSTITUTION-scoped ones (`posts`, `upkeeps`, `priority`,
`watch`, `roster`, `decisions`, `economy`, `structure`, `scene`,
`social_norms`, `clock_hours`, `naming`, `active_places`). A person is
therefore addressed as `(charter_key, body_key)` and stored inside an
institution's blob.

Two absurdities follow, and the owner named both: a hermit the Director
invented needs an institution to exist in, and a person moving town, joining a
crew or transferring ship must be re-keyed across two blobs dragging fifteen
stores with them. A person holding posts in two institutions cannot be
expressed at all.

The shape: hoist the person half to the REGISTRY level so charters reference
bodies rather than containing them, leaving posts, upkeeps and the watch bill
in the charter and making membership the link. A hermit is then a person with
no membership; a transfer is a membership change with identity, memory and
relationships untouched. `registry["items"]` and `_body_refs`'s
`(charter, body)` resolution are half of the addressing already.
`cross_charter_gossip` exists because information already has to cross
institutional boundaries; people should be able to as well.

Cost, stated honestly: the largest single change on this register. Every one
of the fifteen stores moves, `normalize_charter` splits, and it crosses the
persistence boundary -- archive, checkpoint, branch/clone ID remapping. A
cheaper intermediate exists (a `member_of` field plus an atomic transfer
operation moving the fifteen stores between charters) and is explicitly NOT
the plan: it is a migration that gets paid for twice, the second time when
transfers turn out to be ordinary rather than exceptional.

**It is load-bearing for the background consolidation.** The owner's decision
that every background NPC becomes a Charter body -- measured cause: 84 ad-hoc
stateless presences against 14 charter-backed in the corpus, so 86% of
background people reach none of this work -- makes rootless people the COMMON
case rather than the exception. Doing the split afterwards would replace an
86%-stateless problem with an 86%-awkwardly-housed one. Order: split first.

**Timeskips should hand a major character to Charter.** Ask the registered
character what they intend over the declared period, seed it as Charter state,
run the institution forward with `simulate_bound=True`, and hand the
accumulated life back. Both halves already exist and were built for the
adjacent case: `charter_run.step`'s `simulate_bound` suspends the promotion
exclusion precisely because a body nobody is taking turns for should be
simulated rather than frozen, and `charter_promote.promotion_handoff` already
converts accumulated body state into character memories, affect and
relationships. A timeskip is a temporary demotion and re-promotion with an
intent query in front of it.

What is NOT yet decided: whether the intent query is one call or one per
character; how a character's existing projects and intentions seed Charter's
own wants rather than being restated; and what happens when the institution's
simulation contradicts the stated intent, which is the interesting case and
probably the point.

<a id="unbuilt-1-99e"></a>

### 1.99e The three tiers, and the chatter already being thrown away

OWNER DESIGNS 2026-08-27, following 1.99d's split. The intended shape is one
substrate and two presentation layers:

  * **Charter is every unregistered person, always.** Measured cause: 84 ad-hoc
    stateless background presences against 14 charter-backed across the corpus,
    so 86% of background people reach none of the memory, familiarity, ties,
    marks or history-reading volition built for them. `with_charter_presences`
    already OVERLAYS charter bodies onto the presence ledger and is careful
    about identity; what is missing is that a person the Director invents
    mid-scene becomes a name in a dict rather than a body. Minting into Charter
    instead also dissolves the display-name collision problem (Charter keys by
    body id), and the "translate what a presence experienced offscreen back
    into Charter ledgers" problem, which stops existing.
  * **Background life voices whoever is actually being interacted with**,
    rather than the N most salient. The owner's correction: make the handoff
    DYNAMIC -- the player addresses a charter body, or a charter body acts
    toward the player, and that body gets voiced for the beat. Demand-driven
    rather than budget-driven, which also makes `max_managed` far less
    load-bearing than picking a fixed N would. The measurement it still wants
    is what a manager call costs at 4 / 8 / 16 presences; nobody has taken it,
    and the current 6-default / 8-cap is unmeasured.
  * **Crowds carry the rest.** `world/crowds.py` is already the right object --
    one row whatever it contains, band rather than integer, density derived
    from band and room, keyed by uid never display name, with `emerge` and
    `absorb` as the individual/collective bridge. It has ZERO references to
    charter today. Charter knows who is where and, since this week, who has a
    tie, a grievance, a mark or a shared history with whoever is present --
    which is exactly the selector for who steps out of the crowd. Constraint:
    the crowd must be a PROJECTION of Charter's population, never a second
    source of truth about it.

**AMBIENT CHATTER: BUILT 2026-08-27** (`background-presentation` branch), per
`docs/design/DESIGN_BACKGROUND_PRESENTATION.md` Part A. The undecided question
below was settled the way the note argues: structured observations through the
perception layer -- `charter_run.step` deposits the last window's acts
room-stamped as `window_acts` (the transient `acts` died at every
`normalize_charter`, so the durable field is new), and
`agents.common.chatter_for_room` derives a HUM band plus at most ONE overheard
fragment per observer-room-beat, delivered as `hearing` percepts so
`observations_from_render` makes character receipt legitimate.
`charter_news.WITNESSABLE` deliberately did NOT grow a speech kind: at the
measured 19 acts/window against ~5 co-present bodies that door deposits ~100
claims per window into heads whose caps and decay would churn on noise; the
witness rule and the perception route are the same presence rule at two tiers.
The hum's band floor and the
fragment-suppressing density read BOTH crowd species -- authored ledger
rows and Part B's derived charter crowds (found in review: reading the
authored ledger alone left a charter-only story's derived throng with no
hum floor and its derived crush still admitting ordinary fragments;
pinned in `tests/test_charter_chatter.py`).
Residuals, from the note's own open questions: the fragment's seeded rate
(`FRAGMENT_ODDS = 4`) is a prediction awaiting play; the hum thresholds are
vocabulary set once from the §0 measurement (room median 4 / p90 6 acts);
per-observer "has met" recognition is approximated by the story-level
presence ledger -- a FIREWALL residual, not only a naming nicety: once any
beat has presented a charter body individually, every later observer in a
room it talks in receives its display name in the fragment, met or not --
an additive per-observer grant in a system whose guards subtract, and one
the composer's unearned-name tripwire cannot catch because charter display
names are not roster identities. It matches the existing floor (Director
prose already names presences story-wide, and no per-observer met-ledger
exists for charter bodies); if tightened later, the `known` recognition
map -- the engine's one per-observer name-learning ledger -- is the
vocabulary to route it through. *Amended 2026-08-29: that ledger now
CARRIES charter bodies in both directions -- an introduction resolves and
places them (`commit_common.charter_recognition_projection`, read by both
`commit_mapping` and `commit_memory`), so a presence can hold a row of its
own and be held in somebody else's. The chatter fragment still does not
consult it; what changed is that there is now something to consult.*

**THE CROWDS BRIDGE: BUILT 2026-08-27** (`background-presentation` branch),
per the same note's Part B. A charter crowd is a read-time projection —
`world/charter_crowd.py` derives it inside `crowds_for_room` from the
registry bodies at the observer's room minus everyone individually presented
(bindings, live presence records), and NOTHING is persisted: uid minted from
`(chat, charter, place)`, band from `crowds.count_band` (the one place an
integer meets the band vocabulary), composition from the watch bill's role
nouns, mood from banded `strain_of`. `apply_ops` refuses `move`/`split`/
`disperse`/`set` on a derived uid; `emerge` resolves at the commit seam
(`persist/commit.py` → `emerge_from_charter_crowd`) by persisting the
`with_charter_presences` overlay record — the record IS the emergence, no
`emerged` list — with an entanglement-ranked engine pick when `who` is
empty; `absorb` deletes only a record nothing durable names. `MAX_CROWDS`
still governs the authored ledger alone.
**B2's other clause landed 2026-08-28**, having been stated in the note and
built nowhere: "a charter body is ground exactly when nothing this beat
presents it individually" is a SUBTRACTION, and the presentation it
subtracts for did not exist — perception's co-present body roster was the
cast and the players, so a body with a live presence record left the crowd
and entered no view, and "below the floor of the smallest band, members
present as individual ambient figures" had no implementation.
`agents.common.presence_figures_for_room` is the complement of
`crowds_for_room` (ledger people standing here whom `presence_room` places
in the room and `presence_has_an_identity` calls people, plus charter
bodies no derived crowd carries — including when `CO_LOCATED_CAP` drops
that crowd from the view, and excluding a body whose record has LAPSED back
to the ground); `perception._presence_bodies` places them on the stage's
scene copy, because `room_of` fails closed for a body the scene puts
nowhere and every spatial guard begins there. Bound by the room and nothing
else: ledger rows already standing here plus at most
`CHARTER_CROWD_FLOOR - 1` per co-located institution. Measured on chat 98
(bench.db, 2026-08-28): a lounge holding five crew composed as `[]` crowd
and no bodies at all, and two bodies had stood unseen on the bridge since
turn 0. `tests/test_presence_standing_in_the_room.py`. Residuals:
`CHARTER_CROWD_FLOOR`
(3) and the mood bands are predictions awaiting play (DESIGN_CROWDS §7's
falsifier is the measurement); institution-level crowd motion — the
`heading`/`drift` half, a mass surging through Charter's own
conduct/intervention seams — is named in the note (§B4, open question 5)
and deliberately not designed; and `DESIGN_CROWDS.md` §3a's "an emergence
may not be re-met" is SUPERSEDED for charter-backed crowds (amendment in
that note): a fixture is simply a charter body with a post here, and
re-meeting an emerged body is correct, because Charter never stopped
simulating them.

**DEMAND-DRIVEN VOICE: BUILT 2026-08-28** (`background-presentation`
branch), per the same note's Part C. The voice tier voices only whom an
authored mind's own conduct calls on this beat: `pick_voice_demand`
(`persist/commit_background.py`, wrapped by `pick_background_reactors`)
qualifies on exactly four triggers -- addressed (overt declaration, flow
ref, aimed character line, or a Director-routed hand-off), owed an
unexpired reply, acted toward an authored mind last beat (`engaged_turns`
on the record, written at commit; the charter half reads `window_acts`
whose `other` is a bound body or authored figure), or emerged from a crowd
this beat (the provisional `emerge` op, resolved read-only through the same
pick commit runs) -- ordered addressed > owed > acting > emerged, tied by
the B3 entanglement digest, then stably.
**CHANNEL FILTER ADDED 2026-08-29** (`fix-background-gate`). Co-presence is
still not a TRIGGER; it is now a FILTER. A trigger says a demand was
RAISED, not that it arrived, and two of the four are debts accrued on an
EARLIER beat -- so `owed` and `acting` were discharging from anywhere in
the world, and the player's raw-text address was read with no test that the
words carried. `demand_reaches` (`persist/commit_background.py`, applied in
both `pick_voice_demand` and `agents/background._demanded_presences`)
requires an authored mind within FULL hearing of where the presence stands
-- the same bar `_character_address_of` and the reply-debt writer in
`track_background_presences` already used, so the gate and its own debt
writer stopped disagreeing. Exempt: the Director's judgment for THIS beat
(`routed`, a flow address, an emerge), because a hand-off that becomes
silence is the failure the gate exists to end; and an aimed character line,
which passed a stricter version of the same test. Fail-OPEN for an
UNPLACED presence and only that one -- a room the scene does not
contain fails CLOSED, because `spatial_rel` reads an unknown room id as
separated and `hear_level` grades that `none`. (Corrected 2026-08-29:
this paragraph, the `demand_reaches` docstring and `Design.md` all said
"unknown rooms fail open", and the measurement says otherwise --
`demand_reaches` with a room name absent from the scene returns False,
with `here=""` it returns True.) Measured by replaying the gate against all 40 recorded
turns of chat 98 (checkpoint world state per turn, the recorded
`director_interpret`/`director_resolve` of that turn; the replay reproduces
the recorded `selected` list on every turn before the change): 29 of the
run's 51 voice calls went to one body on the engineering deck that
qualified on `acting` for 14 consecutive beats -- including turn 36, with
the player two decks away addressing five presences at her own table -- and
produced not one line. All 29 are gone; every pick that ever produced a
line survives, including turn 23's, where the player was in a lift one open
door from the engineering deck. `tests/test_voice_demand.py::
TestADemandOnlyCountsWhereItCanArrive`. `mentioned` (prose salience),
bare `dialogue_turns` (tenure) and `at_post` (co-presence) stopped
qualifying; `scene_life`'s roster is the same demand set
(`_demanded_presences`) and `max_managed` is a ceiling, not a selector. An
addressee is never dropped: precise addresses widen the slots, and
addressees past the ceiling that share one derived charter crowd answer AS
that crowd -- one deterministic, model-free chorus entry, nothing
persisted, reply debts discharged through the entry's `addressed` list.
No tenure: K = `charter_crowd.PRESENTED_IDLE_BEATS` (4) idle beats lapse a
record's individual PRESENTATION (crowd membership counts the body again;
recognition -- `known_bodies`, naming -- never lapses; nothing is
deleted), measured per the note's instruction from every live chat's
presence ledger (2026-08-27 engine.db: 25/28 = 89.3% of resumptions after
real inattention came within 4 idle beats; n = 28, re-take as the corpus
grows). Measured before/after on twin_towns(40) plus six at-post regulars
(30 quiet + 10 mention + 10 addressed beats): per-presence voice calls
50 -> 10 per 50 beats (quiet and mention beats now spend zero), manager
cast entries 300 -> 60, and the old gate answered "Regular 2, what do I
owe you?" with Regular 5 (recency outranked the addressee) where the
demand gate answers with Regular 2 -- the precise/loose address split that
measurement forced is in `_background_name_named_exactly`. Gate cost 75ms
vs 42ms per beat (two more registry reads), against the ~22.5s calls it
gates. `tests/test_voice_demand.py`. Residuals: the chorus degradation
exists only for charter-crowd-shaped addressees -- tracked individuals or
mixed institutions past the ceiling widen instead (no crowd object to
answer through);
**AN ADDRESS TO A CROWD THAT NAMES NOBODY QUALIFIES ON NOTHING, and it is
the loop the player actually hits.** Every one of the four triggers needs
a name or a ref: `flow.addressed_to` accepts a name string for an
unregistered presence, and the Director IS shown who is addressable
(`director_interpret`'s `addressable_presences`, derived per the player's
room), but a player who has only been shown a band cannot name anybody and
the Director is under no deterministic obligation to pick. Measured live,
chat 98 (bench.db) turns 11-13: five crew derived at the player's lounge,
`addressable_presences` therefore holding all five with
`same_room_as_player`, a crowd row with its uid in `_crowds_view`, the
player speaking to them across a table on three consecutive beats -- and
`addressed_to: []`, `intended_target: null`, `crowd_ops: []`,
`routed_to_background: []`, `background_react` `{"fired": false,
"agent_calls": []}` every time. Nothing in the engine failed a check; there
was no check. `emerge` is the design's loop-breaker (B3) and it is
model-gated end to end, so the deterministic floor that turns "someone was
spoken to" into "someone answers" stops at the crowd's edge. Whether the
answer is a demand trigger for an overt line in a room whose only other
occupants are one crowd (with the obvious over-firing hazard: a player
muttering in a plaza must not summon the plaza), a Director obligation, or
a chorus reached without an addressee list, is undesigned. Do not read the
2026-08-28 figures work as having closed this: it fixed who is COMPOSED,
not who may be AIMED at;
and the §C4 manager-call latency measurement remains
UNTAKEN (this workflow runs no live models). Its protocol, verbatim so an
evening can settle it: one seeded scene, `max_managed` forced to 4 / 8 /
16 with the demand filter off, 10 calls each against the live
`agent_models` (read live -- they change), report median wall-clock and
OUTPUT tokens, which the note argues is the dominant unmeasured term (the
~22.5s character call is the same family). Prediction to falsify:
wall-clock grows with cast mostly through output, in which case
demand-driven voicing caps the cost directly and `max_managed`'s default
is nearly irrelevant; if it instead grows with input, the ceiling is
load-bearing and should be set from the curve.

<a id="unbuilt-1-99f"></a>

### 1.99f A companion arrives having never met the player

OWNER'S CATCH, from the market-town playtest 2026-08-28, marked for later
rather than fixed.

A character attached as the player's TRAVELLING COMPANION -- briefed as
somebody who has been on the road with them long enough to have opinions about
it -- arrives knowing nobody. Measured on chat 95 after seven beats:

  * the companion's only relationship edge is to `"person of unremarkable
    appearance"`, at trust 0.06 and familiarity 0.09, with
    `last_interaction_turn: 4`. That is the PLAYER, met as a stranger, during
    play.
  * ZERO of the companion's memories mention the player by name.

`story/journey_history.compile_journey_history` generated sixteen events of
road and a summary, and the route brief explicitly said "events the player was
present for should read as shared". The generator has no reason to put the
player in them: it is handed the character's sheet, the lore and an arrival
brief, and nothing that says who else was walking. So it wrote one person's
past, correctly, and the shared half does not exist.

The visible symptom is narration: for three beats the narrator called the
companion "the wiry man" and "the wiry figure" while `speakers` knew him as
`('major', 'Jonas Reed')` -- rendering a stranger because, in every ledger the
narrator can read, he was one.

WHAT IS MISSING is mutual history at attachment: the player named in the
companion's journey events where the brief says they were present, a
relationship edge seeded in both directions rather than formed on contact, and
-- the open question -- what the PLAYER remembers, given a persona has no
memory bank of its own. The last is the part that needs deciding before any of
it is built.

Do NOT confuse this with the companion acting on his own agenda. He declared
an intention on beat 1, went to the wharf against the player's direction, and
by beat 4 had independently found the river running two hand-widths high and
started a thread nobody scripted. That is a mind doing its own things and is
the system working; the owner said so explicitly. The gap is only that he does
it as a stranger.

<a id="unbuilt-1-102"></a>

### 1.102 What reaches a charter voice: what the 2026-09-03 fix reached, and what it did not

Landed: `commit_charter_observations` receives the scene (it received the
prepared-commit envelope and every actor was unplaced -- `acquired: 0` on all
forty Harrowmere turns), co-presence sighting runs live
(`charter_runtime.sight_figures_in_scene`), a figure is one subject keyed by
the canonical name and rendered per observer, carrier news is stamped on the
charter's own clock, and `own_state` reaches the per-presence voice.
`tests/test_charter_voice_context.py`. Left open:

- **The scene-manager path carries no charter slice.** `background.scene_life`
  (`scene_life: ambient|full`) builds its populace from presence records and
  never calls `presence_view`, so under the manager a body has no news, no
  acquaintances and no `own_state`; only the per-presence `background_react`
  path hands the slice over. The manager voices several bodies in one payload,
  and one slice per body in a shared context is the cross-contamination §3.2
  forbids, so this needs a per-body scoping decision, not a copy of the call.
- **Charter-native events still cross to `world_events` in charter hours.**
  `charter_hours_of` converts the carrier rail's seconds INTO a mind;
  `land_presim` already converts presim events OUT by the horizon; the live
  `advance_snapshot` path that mints `world_events` rows from window events
  was not audited for the same unit.
- **A name a charter body has learned is not yet rendered as the name.**
  `presence_view` renders a figure in whatever label the caller hands it, and
  `background._react_one` hands the name only where the presence's `known`
  entry carries it -- which `seed_mutual_recognition` writes for cast
  memberships and nothing writes for an unpromoted body told a name aloud.
  The slice is right and safe (the stranger label); it is merely never the
  name.

<a id="unbuilt-1-103"></a>

### 1.103 The player's dealings with a townsperson: what the ledgers do not yet answer

Landed 2026-09-03 (`charter_author.FIGURE_ACTS` widened to order, request,
bargain, promise, trade, give; `tests/test_figure_acts.py`). Four residuals,
each a decision rather than a defect:

  * **A body's answer does not trigger its own voice.** `bodies_acting_toward_
    authored` reads `window_acts` rows whose `other` is a persisted figure
    key, and figures are injected per call and never persisted, so an act
    answered at commit does not fire the §C1.3 "acting" trigger next beat.
    The voice reaches the answer two other ways -- the owed-reply debt the
    same utterance wrote, and `presence_view`'s same-beat `answers` preview
    -- so nothing is lost for a spoken act; a GIFT with no words is taken in
    the ledger and voiced only if something else demands it.
  * **Trade is one lot, bought.** `plan_figure_acts` fixes `quantity` at 1
    and the figure as buyer; selling needs the figure to hold stock under its
    own key in `economy.stocks`, which only an earlier purchase gives it.
    Quantity is not read from prose on purpose (a word list) and no channel
    carries it yet.
  * **A gift is read only from `inventory_ops`.** The playtest's five coppers
    (t9) were an ACTION row the objects hand wrote no op for; they are no
    gift and no trade. That is the objects hand's miss, not this seam's, and
    the chunk now tells it a listed person is a body it may hand things to.
    The replay's t5 letter arrived as a containment record instead (the
    contact hand's door); the THING now follows the reeve (1.101), but the
    ledger records no `give`, because a grasp is not a gift and only the op
    says one was made.
  * **The reader, after the 2026-09-03 replay.** Fixed: a compound kind
    carries every kind it names, a determiner is not a word of a name, a
    role noun resolves through the post's authored forms, a posted body
    outranks an ambient shadow (`tests/test_figure_act_reading.py`). Left,
    each named in its docstring: the interpreter's communication verb
    ("ask", t18) is its own vocabulary, kept as written, and names no public
    kind, so it reaches no ledger -- t18's "ask whether he would have his
    clerk pull the rolls" was in substance a request, and reading the verb
    as one is a synonym table; the social hand's own kind outside the
    vocabulary is `other` and WARNED by name; a role noun with no form in
    common with the post ("the blacksmith" against `smith`) reaches only an
    ambient shadow; and a duty that names the people it acts on ("turns
    back drovers") makes that noun a form of the post, so "the drover" said
    in the watchman's room reaches the watchman -- widening the authored
    duty vocabulary into subject and object is the charter model's question.
  * **The Director's preview names three dealings and no trade.**
    `PREVIEWED_DEALINGS` is order, request, bargain: a trade needs a good
    the beat has not named yet, so the Director learns a price only from
    the voice's own `answers` (which run the full plan). The preview is
    computed for the PLAYER as asker; a cast member's dealings are previewed
    to nobody but the voice.
  * **Standing is the `reports_to` chain, and a persona rides nobody.**
    `has_standing` reads bindings (a promoted character riding a body) and
    members acting as figures; a player persona who IS the reeve by
    authorship has no binding and no standing, so their orders are requests.
    Giving a persona a body to ride is the promotion seam's question.

<a id="unbuilt-1-105"></a>

### 1.105 The off-screen ladder should collapse to one toggle, and it has five rungs

**Ruled by the owner 2026-09-04**, in three parts. The first landed with the
ruling; the other two are what is left.

**Charter is unconditional, and that is done.** `schedule_charter_ticks` no
longer reads the `offscreen_life` ceiling. Charter is where an unwatched body
lives rather than a mechanism a rung may switch off, its advance path holds no
provider seam at all, and the ladder is a SPEND gate -- so the rung was
withholding free work, and a host lowering it to save money froze the town
instead of saving anything. The only reason the tick does not run is
`charter_skip: "no_charters"`.

**The host-facing collapse landed 2026-09-04**, with the owner's ruling that
the villain ladder stays as a placeholder. The panel asks one question, *allow
off-screen cognition*, and `dialogue_config` derives the rung: `reactive` off,
`character_agent` on. The five rungs survive as the MECHANISM, because
`living_world`'s four approaches are written against them and
`provision_story(offscreen_life=...)` is a published extension contract -- so
nothing that reads the ladder had to change, including
`artifacts.schedule_artifact_text` and the two tick schedulers.

**The other half of the ruling: the toggle should enable the playerless
causality bubbles. THE BUBBLES LANDED 2026-09-17** (`world/spatial_bubbles.py`
plus the couple drivers in `world/spatial_frames.py`,
`docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md` § 3 / § 4.1): a major character
who walks into a zone with no human in it gets a frame, a live comm channel
fuses that frame with the player's for as long as the call lasts, and walking
back ends the separation. **The TOGGLE has not moved and the ladder has not
retired.** Today it still enables the machinery the bubbles replace --
`offscreen.schedule_profile_ticks` and `schedule_agent_ticks` -- and a bubble
fires on the zone rule alone, under no toggle at all, exactly as a party split
always has. Moving the toggle's meaning is § 4.2-4.4 and § 5 of that note, and
those wait on a play run: nothing in the corpus has run a bubble yet.

**One behaviour change, stated because it is easy to miss.** A chat that never
opened the panel used to sit at `stochastic`; it now rides the toggle's default
and sits at `character_agent`. Nothing new fires from that alone: an agent tick
additionally needs the card's `simulation.offscreen_agent`, the antagonist
ladder at `ceiling` (default off), dormant status, a non-zero
`max_offscreen_actors` and a private reason. A chat that STORED a rung keeps
it, so no configured story moved.

**On-screen voicing is already default and already bounded by a count, and
the panel does not say so.** A charter body in the player's room reaches the
ordinary per-presence path -- `with_charter_presences` merges derived charter
identities into the presence set before the demand gate, at every `scene_life`
level including `off` -- so it speaks when the beat demands it, capped by
`background_config.max_reactors` (default 1, hard ceiling 3). What `scene_life`
buys is a different thing entirely: ONE batched call voicing several presences
coherently. `ambient` is firewall-safe by construction, since the manager's
context holds only what every managed presence legitimately shares.

**The open decision, and it is the owner's:** should `scene_life` default to
`ambient` rather than `off`? It is the only remaining sense in which on-screen
voicing is not default. It costs one batched call on beats with a demand set,
against N per-presence calls today, so it is plausibly cheaper as well as more
coherent. `full` is a separate question and does not follow: it hands the
manager directed lines tagged with their audience, which relaxes an
information rule, and by the standing invariant a leak must be an engine
failure rather than a model's.

<a id="unbuilt-1-108"></a>

### 1.108 What the Living World audit found

**Found:** the 2026-08-24 survey behind `docs/guides/LIVING_WORLD.md` — eleven
agents over `world/living_world.py`, `world/offscreen.py`, the twenty-nine
`charter_*` modules, background life and the lifecycle paths. The guide states
the behaviour; these are the places the behaviour is wrong.

**Defects.**

- ~~**The string `"false"` opts a character INTO paid off-screen ticks.**~~
  **Landed.** `character_schema.authored_bool` reads the word a human wrote,
  both card readers use it, and `character_card_warnings` tells the author
  that whatever produced the sheet is not writing booleans. Original finding:
  `character_offscreen_agent` applies `bool()`, and `bool("false")` is `True`.
  The legacy branch applies the same `bool()`, so neither path is safe
  (`story/character_schema.py:1166`, `:1400`). An imported or hand-edited sheet
  carrying `"offscreen_agent": "false"` buys model calls. The card default is a
  real boolean, so this reaches only sheets that have been through a text
  editor or a lenient importer — which is exactly where it will not be noticed.
- ~~**Two `cap=0` off-by-ones**~~ **Landed** — both now bound before they
  append, matching `profile_candidates`, which already did. Original finding:
  `full_agent_candidates(cap=0)` returns one candidate
  (`world/offscreen.py:1338`) and `fired_consequences_at(cap=0)` returns one
  item (`world/living_world.py:463`). Unreachable from today's callers, which
  guard `cap <= 0` first; inherited by any new caller. `profile_candidates`
  has the correct shape beside one of them (`:1399`).
- ~~**Charter diagnostics leak across frames.**~~ **Landed** —
  `charter_runtime._event_frame` filters the listing to the requested era, in
  Python because `scheduled_events` has no frame column and the scoping rides
  in the payload. Original finding: `charter_diagnostics` selects
  `scheduled_events` with `seed LIKE 'charter:%'` and no `frame_id` predicate
  (`world/charter_runtime.py:1161`), so the diagnostics surface for one era
  lists charter events minted in every era of the chat — unlike `registry_for`
  beside it, which is frame-scoped.
- **Frame split and merge drop Charter and off-screen state.** A split seeds
  the away frame from seven parent keys and `charters`, `offscreen_epoch` and
  `offscreen_plans` are not among them (`world/spatial_frames.py:844`); a merge
  reconciles four keys, so nothing a Charter, a plan or a standing intention
  did in the away frame comes back (`:998`). Whether that is a defect or a
  deliberate severance is undecided — it is undocumented either way, which is
  the part that is certainly wrong.
- **`pick_background_reactors` has no room filter.** `here` is computed and
  used for only two of the eight qualifying signals
  (`persist/commit_background.py:1541`), so a presence with dialogue history in
  a room the player left ten turns ago still qualifies and can be picked.
  `managed_presences` DOES filter by ambient scope
  (`agents/background.py:553`), so the two paths disagree about co-presence.

**Untested.** No test in the suite covers Charter, Living World or off-screen
state across archive, branch or checkpoint. The coverage is real — every table
and key involved is in `chat_archive.WORLD_TABLES` and
`checkpoints.snapshot_state` — but it is inferred from those lists rather than
demonstrated, and the frame-split gap above is what an untested inference
looks like when it is wrong.

~~**Unwired.** `world/structure.py`'s frontier-expansion trio —
`materialize_planned_fringe`, `prepare_frontier_expansion`,
`apply_frontier_mutations` — has no production caller.~~ **Stale, corrected
2026-09-05:** all three run every beat from
`persist/commit_scene_state.prepare_scene_commit` / `commit_scene`.

**Docstrings that overstate, each now contradicted by the guide.** Fix the
docstring or fix the code; do not leave both.

- "five approaches" in `world/living_world.py:1` and `web/app.py:4547` —
  `LIVING_WORLD_APPROACHES` has four. Approach C became core carrier physics.
- ~~`pick_background_reactors` returning `[]` as "the common case"~~ —
  **withdrawn, and worth recording as a method note.** The audit reasoned from
  the code that `dialogue_turns` is a standalone qualifying signal and records
  are pruned only by promotion, so any presence that has spoken once qualifies
  forever. The reading is right and the conclusion is false: measured over 816
  live `background_react` steps in nine chats, the backstop produced a reaction
  on 0–10% of beats, and 41 of 69 tracked presences have non-empty
  `dialogue_turns`. Something downstream of that disjunct — the `roster` /
  `voiced_this_beat` exclusion is the candidate — keeps it quiet. The
  docstring stands. A code reading is a hypothesis; this corpus can answer it
  directly, and the first draft of `LIVING_WORLD.md` shipped the hypothesis as
  fact.
- `ambient` withholding "a line directed at one of them"
  (`story/scene.py:2087`, `agents/background.py:559`) — the test is divergent
  hear levels, not direction.
- `agents/background.py:16` naming the gate `pick_background_reactor`
  (singular); the stage calls the plural with `cap`.
- `agents/background.py:32` calling `pending_reply` "a one-beat debt"; the
  write sets `expires_turn = turn_idx + 2`.
- `world/charter_run.py:20` saying the consequence-fuse wiring is "deliberately
  NOT done here" — it exists, in `charter_runtime`.
- `world/charter_model.py`'s "five primitives" headline, against four
  normalizers, with `normalize_body` outside the five; and its `authority`
  described as "a closed list" where `normalize_post` closes nothing
  (`:145`). The real closed set is `charter_decide.ORDER_ACTIONS`.

<a id="unbuilt-1-111"></a>

### 1.111 Every charter already written names no commons

`world/charter_space.commons_places` and the `commons` field it reads are new,
and the field is EMPTY on every institution generated before it existed. So the
class is closed -- a place a body may go for its own sake is now expressible,
`frequented_places` is what `reach_map` walks and `errands` filters against, and
`charter_runtime.registry_warnings` says out loud when an institution has none
-- while every already-generated world still routes its whole off-duty
population to somebody's workplace until an author names its rooms or the
location is regenerated. That is the authored-blank shape `CLAUDE.md` records
for psychology, which is why the warning landed with the field rather than
after it, and it is a MIGRATION rather than a defect: nothing can derive the
predicate from what a charter already stores. A room's `purpose` is free prose
and `world/place_purpose.py` states the reason not to key on it -- names are
short noun phrases where identifier recognition is honest, descriptions are
where it lies.

Two things the field is deliberately not.
  * **Not berths.** A berth is somebody's own place rather than a place people
    go, `charter_move.homecomings` already routes a body to its own without
    consulting reach, and the set of distinct berths grows with the population
    -- on `tests/charter_worlds.big_town(1000)` every body's berth defaults to
    its authored place, so folding them in would take `reach_map` from 1000 x 6
    pairs to 1000 x 109.
  * **Not `active_places`.** That is where social detail is simulated at beat
    resolution, a scope dial, not a statement about what a room is for.

Measured on chat 98: 7 work places against 45 rooms, and the run's author had
to invent an upkeep nobody serves (`wardroom_service`, `requires: {}` -- a
condition the institution now owes forever and will report as failing) purely
to say that people sit in a lounge.

<a id="unbuilt-1-115"></a>

### 1.115 The needs filter reads free prose, and its threshold is a judgement

**Built 2026-09-05** (`commit_mapping._drop_needs_the_beat_answers`, closing
the person-and-thing half of the caravanserai run's PB11 and the flat run's
PE10). A person- or thing-need answered by what the beat was already holding
is no longer filed: a thing the scene places in the room the need names, or a
`present_figures` body sharing two or more content words with the subject.

Two things are registered rather than solved. **The threshold is a
judgement**: a body and a subject are matched on words in common, which is
exactly the guard family that failed four times on 2026-08-29, so it fails
toward FILING -- one shared word is a coincidence between any two English
nouns, and a need wrongly dropped is a body nobody plans. A structural answer
exists in principle (`charter_surface.surface_of` is a per-axis store and
`charter_crowd.member_noun` is what a body IS, so the subject could be matched
against closed per-axis vocabularies rather than a bag of words) and was not
built here. **And the `setting_fact` half of PB11 is untouched**: a fact the
scenario text already states still files a need that reads as a missing
object, which is F4's legibility class and is registered with it.

<a id="unbuilt-1-123"></a>

### 1.123 An errand the fiction promised has no channel to the institution

**CLOSED 2026-09-05, as a duplicate of § 1.124 with its Planner half built.**
Two things happened to this entry. First, it and § 1.124 are one gap written
down twice on the same day, and § 1.124 is the sharper statement of it; what
remains open lives there and nowhere else. Second, the half this entry
actually asked for — somebody with a channel to the institution — landed as
the PLANNER's, not the Director's: `charter_ops`
(`world/charter_ops.py`, `charter_runtime.author_charter_ops`,
`tests/test_charter_ops.py`) is a package operation carrying one authored
event, and `errand` is one of its eight ops, routed through
`charter_surgery.send_errand` and refused by name when the body is not one the
town stands or the destination is a room no plan holds. The "cheaper half"
this entry offered — a Director-sheet clause — is still worth having as a
COMPANION and is recorded in § 1.124, which is where the Director channel
stays open.

The original entry follows, because the argument in it is what earned the
shape that landed.

**Found 2026-09-05** (`docs/experiments/PLAY_2026_09_05_caravanserai.md`
§ PB13), and registered rather than built: this is a CAPABILITY, not a
defect, and the shape is the owner's to choose. Its siblings — PC9, PC5,
PB10 and PE12 — were all "a hand could see something true and had no channel
to say it", and all four landed the same day; this is the fifth, and the
only one where the missing channel would give the Director a new kind of
authority rather than a new way to write down what it already rules on.

**Measured.** Turns 5 and 10: the player asked twice that someone fetch the
gate warden; the innkeeper agreed on the record ("She'll be told when the
rush settles", "The girl at the tap can call him") and the Director's prose
said she was "signalling the serving hand Neris to attend to it". Nothing in
`state_diff` carries it — `sv_neris` has no `walk`, no `errand`, an
unchanged `place`, and the warden was still at his bench on turn 14. The
`errand` operation EXISTS (`plot_packages.OPERATION_FIELDS`,
`charter_surgery.send_errand`) and only the Writers' Room can author one, so
the fiction and the ledger disagree from the moment an NPC is asked to do
anything.

**The shape, if it is built.** A `charter_ops` channel on the resolve,
owned by the `social` specialist — it already holds `crowd_ops`,
`courier_ops` and `telling_ops`, which are the same kind of thing (speech
and roster work whose SIMULATION belongs to charter), and it is already the
one hand shown the traffic ledgers and the room index its ops would name.
One op to start with, `{op: "errand", who, to_room, purpose}`, routed
through `charter_place`/`charter_move` exactly as `positions` and `stations`
already route through `charter_place.resolve_scene_placements`, and refused
the same way: an errand naming a body the town does not stand, or a room no
plan holds, writes nothing and says so. Fail-open — absent means today's
behaviour, and no scene without a charter changes.

**The cheaper half, if it is not.** One clause in the Director sheet stating
the class: an instruction to a townsperson is realised as a write this beat
or it is not narrated as agreed. That costs nothing and stops the ledger
contradicting the prose, at the price of the fiction being unable to promise
an errand at all. PB12 (the institution never ticks at conversational pace)
is the reason either answer matters: at ~18 story-seconds a beat no charter
window is ever charged, so even a dispatched errand would not walk.

<a id="unbuilt-1-124"></a>

### 1.124 The Director dispatches an errand to an institution (PB13, BUILT 2026-09-05)

**Found 2026-09-05** (`docs/experiments/PLAY_2026_09_05_caravanserai.md` §
PB13), registered rather than built: the shape needs `llm/schemas.py`, which
another agent held on the day PB12 was fixed.

**BUILT 2026-09-05, the same day it was narrowed.** `charter_ops` is now a
channel of the SOCIAL specialist -- one closed op vocabulary
(`world/charter_ops.py`), two authors, which is the point of routing the
Director through the Planner's own landing function rather than giving it a
second one. The registries that make a channel real all name it: `StateDiff`
and `DirectorSocialSpecialist` in `llm/schemas.py`, `SPECIALIST_CHANNELS`,
`director_scopes.SPECIALISTS`, `director_evidence._SUBJECT_OP_CHANNELS`
(`body`, `to`), a prompt chunk in both packs, the prose author's delegation
paragraph, and the two test ledgers that say what payload shows the hand its
own state and why an order is not a manifest category (a dispatch changes
nothing until the body has walked it).

Routed exactly as a townsperson's `positions` entry is, and for the same
reason: the ops are stripped from the diff in `prepare_scene_commit` before
the merge, because the scene has no row for any of it, and landed by
`_apply_charter_orders` inside `commit_scene`'s transaction, so a rollback
takes them with the scene. A story with ONE institution does not make the
hand name it -- the engine knows which, and an op refused for a field the
beat could not have known is a refusal the fiction cannot act on. A refusal
anywhere reports the WHOLE event and applies none of it (`author_charter_ops`
is all-or-nothing), reaches the Director through `tell_director`, and the
beat still commits: a town that could not take an order is not a reason to
lose the scene.

**Narrowed 2026-09-05.** The Planner's half is built (`charter_ops`,
§ 1.123), so what is missing here is now only the CHANNEL and not the landing
function: `world/charter_ops.py` already normalizes, routes and refuses an
`errand` op by name, and `charter_runtime.author_charter_ops` already lands a
whole event all-or-nothing. A Director channel is three edits in files this
agent did not own — a `charter_ops` array on the resolve schema in
`llm/schemas.py`, the channel added to the `social` specialist's scope in
`agents/director_scopes.py`, and routing in `agents/director.py` that calls
`author_charter_ops` and sends an unroutable op to `tell_director` rather than
dropping it. The op vocabulary the Director would write is the same closed
set the Planner writes, which is the point of having only one.

Turns 5 and 10 of that run: the player asked twice that someone fetch the
gate warden, the innkeeper agreed on the record ("She'll be told when the
rush settles", "The girl at the tap can call him"), and the Director's own
prose said she was "signalling the serving hand Neris to attend to it".
Nothing in `state_diff` carried it. The registry shows `sv_neris` with no
`walk`, no `errand` and `place` unchanged, and the warden still at his bench
on turn 14. The `errand` operation EXISTS —
`plot_packages.OPERATION_FIELDS`, `charter_surgery.send_errand` — but only
the Writers' Room can author one. The Director owns objective causality and
had just narrated the order, and has no channel to it.

This is now the sharper gap, not the duller one: since PB12 the town does
advance every beat, so an errand dispatched would actually be WALKED, one
room at a time, at a pace the scene can watch (`charter_move`, and the
0.2-of-a-room credit that carries between short beats). Before PB12 the
channel would have written a route nothing stepped.

**Recommendation, for the owner and for whoever holds `llm/schemas.py`.**
Take the first of the two options that play report offered — a `charter_ops`
channel on the resolve — and shape it exactly as `positions`/`stations`
already are, because the routing seam for a Director write that lands on a
charter body rather than the scene is built and tested
(`charter_place.resolve_scene_placements`, `charter_runtime.
route_scene_placements` before the merge, `apply_scene_placements` inside
`commit_scene`). Concretely:

* One op, `errand`, with `{who, to, purpose}` — the body as the beat names
  it, the destination as a room or a place the charter holds, and the reason
  in the institution's own words. `charter_surgery.send_errand` is the
  landing function and already exists; nothing new simulates.
* It belongs to the **`social` specialist**, which owns the traffic channels
  since the `offscreen` hand was retired (2026-09-04) and is the hand that
  already rules on who was told to do what.
* It must FAIL LOUD, not silently: a `who` no charter body answers to, or a
  `to` no room holds, reaches `tell_director` the way an unrouted ledger
  note does. An order the fiction stated and the ledger dropped is the exact
  defect being closed, so the fix must not be able to drop one quietly.
* The alternative the play report offered — a Director-sheet clause saying an
  instruction to a townsperson must be realised as a `positions` write this
  beat or not narrated as agreed — is **not** recommended as the primary. It
  states the class correctly, but `positions` teleports a body to its
  destination, which is the thing `charter_move` was written to stop doing:
  an errand is a walk that takes time and passes through rooms, and
  collapsing it to a position would undo the property that makes it worth
  narrating. Keep the clause as a companion if the channel is built, so a
  beat that narrates an order without writing one is told.

<a id="unbuilt-1-137"></a>

### 1.137 A planned room is deaf until somebody puts a counter in it — BUILT 2026-09-06

**Measured 2026-09-05, descent run.** `sound_field` gates on
`room_has_geometry`, which is the FOV layer's opt-in for the per-observer
furniture sentence and asks whether an ANCHOR carries an authored height. A
room with a measured extent and no anchors -- the ordinary state of every
planned room the Director has not yet furnished -- therefore has no sound
field, and nothing standing in it can hear anything at all.

Live case: the Writers' Room planned a containment annex at 14x12 paces and
filed a creature into it. The player put a pry bar into a door two rooms away
and the beat wrote three `sensory_events`, one of them a `loud` metallic
clatter. The creature heard nothing -- not because of distance or a door, but
because its own room had no counter in it. The service spine, which the
Director HAD furnished, has three anchors and a field.

**The light field already made this exact distinction and recorded the
measurement**: `light_geometry_exists` accepts a size tier or an extent,
"deliberately WIDER than `room_has_geometry` ... light needs a grid and a
place for the source, not a counter to shadow with -- 321/589 live rooms
against 2/589." Sound needs a grid and somewhere to put the source for the
same reason and kept the narrow gate.

**Why it is not simply changed.** Widening it was tried and reverted the same
hour: it turns the near field on for every room carrying a size tier, which
changes hearing in every existing story. Three tests caught it immediately,
and one of them --
`test_a_scene_without_geometry_stamps_nothing_and_composes_byte_identically`
-- exists precisely to hold that promise; another measured a whisper becoming
audible where the model had called it inaudible. That is a behaviour change to
every story, of the same size as the wall-loss recalibration in § 1.125, and
it is the owner's.

**The narrower reading:** the gate could accept an EXTENT (a measured shape)
without accepting a bare size tier, which is what a planned room actually
carries and what the creature case needs, and would leave every room the
engine merely guessed a size for exactly as it is.

**MEASURED 2026-09-06, on the owner's 580 live rooms**, because the light
field's 321/589 is a count for a different gate:

  * the current gate (an anchor carrying a height): **4 rooms, 0.7%**
  * accepts an extent: 9, 1.6%
  * accepts a size tier too: +327, 56.4%

So the near field -- the spreading loss, the noise floor, the masking rule,
the aperture losses -- runs for FOUR ROOMS IN FIVE HUNDRED AND EIGHTY, and
every other room in every story falls back to the barrier-only edge model,
which has no distance within a room and no noise floor at all. The wide
option is therefore not a widening: it is switching the sound model on for
the world for the first time.

**The owner chose the wide option on 2026-09-06** ("the option that gives the
most realistic sound travel ... we have to estimate planned rooms to some
extent, which is fine"), and it is TAKEN: `sound_field` gates on
`_room_grid_exists` (the light field's `light_geometry_exists`, which gained
an extent check the same commit -- it predated extents, and `size_from_extent`
derives the tier FROM an extent, so a measured room with no size word had no
grid for either sense). Descent story: fields on 2 of 10 rooms before, 9 of 10
after.

**IT WAS NOT THE LAST GATE. Switching the field on found three more, each of
which had been invisible while the field ran for four rooms** (all fixed
2026-09-06, all in the same commit, with the run parked on the beat that
exposed them):

  * **A doorway with no bearing places no neighbour, so every composite was an
    ISLAND.** `room_field` lays a neighbour out from the edge's bearing, and a
    bearing is written by a hand that stood in the room. A room the Writers'
    Room planned has never been stood in: the plan schema asks for `{to,
    barrier, distance}` and no bearing at all. Measured across the stories
    live that day (chats 115, 116, and the descent copy): **4 of 54 edges
    carried a bearing, and 0 of the 38 belonging to a planned room.** So the
    near field existed and reached only the listener's own walls.
    `spatial_orientation.derived_edge_bearings` gives a doorway both sides
    left silent a wall -- pairwise, reciprocal, never over a declared bearing,
    eight points to a room and the ninth unplaced. **Sound and light ask for
    it and SIGHT DOES NOT** (`room_field(derive=...)`): a guessed wall shades
    an amount, which is what those two answer, but it MINTS AN OBJECT in a
    list of what an observer can make out, and that would be an engine-made
    fact. `tests/test_openings_in_view.py` already held that line and is why
    the scoping exists.
  * **A room longer than it is wide put its own centre outside itself.**
    `_centre(grid_side(...))` squares the room's LONGER side: a 6 by 24
    service spine answered (12, 12) with six cells of width. Every source
    placed there -- every crowd, every one-beat sound event, every unmeasured
    body -- was off the grid and silently dropped, so **a noise made in a
    corridor reached nobody, the people standing in it included.**
    `spatial_fov.room_centre` asks the room's own grid and finishes through
    `nearest`, so an L or a round room gets a cell it actually holds; a square
    room keeps the cell it always had.
  * **Sounds made in one place masked each other into silence.** A ratio test
    gives each of N equal sources `1 / (N - 1)` of the din, so two in one
    place were marginal and **three were inaudible at any volume** (measured:
    three sources of power 100 against an ambient of 0.05, all three `none`).
    Not a corner: a beat's events are all placed at their room's centre,
    because a one-off noise says which room it was in and nothing finer, so
    every pair of them in one room shares a cell by construction. `noise_at`
    now skips a source standing where the excluded one stands -- two noises at
    one spot reach an ear as one louder noise, and what an ear cannot do with
    them is tell them apart, which is `fragment` against `full` and not
    silence. Two voices from two DIFFERENT places mask each other exactly as
    before.

**And one that was not the sound field's at all** -- found in the same beat
and fixed with it, because it decided what the sound crossed:

  * **A stub's doorway is the plan's guess, and the story never overruled
    it.** A planned room takes its exits from the plan, where the barrier is
    whatever the Room wrote before anybody had been there; when a hand later
    describes that doorway from the room it can actually see, the two sides
    disagree and every sense reads whichever it stands on.
    `spatial_merge._mirror_symmetric_barriers` states the rule for a diff and
    the plan-supply path never met it. Measured, descent turn 13: **six of the
    seven doorways off one service spine disagreed with themselves**, and the
    containment annex -- which the spine records behind a shut `closed_door`
    named "the containment door" -- heard through an `open_door`, because that
    is what its own side still said. `structure._settle_stub_barriers`: the
    plan yields and the story stands, only for a room still carrying
    `planned`, and only to a barrier the other side actually declares.
    Closing it also closed a content leak on its own: with the barrier
    corrected, ordinary speech in the spine no longer reaches the annex at
    all (`normal` -> `none` through a shut door), where before the creature
    standing there was receiving `witnessed_speech` claims carrying both
    characters' exact quotes. The class that leak belongs to is § 1.139.

<a id="unbuilt-1-139"></a>

### 1.139 A creature holds the words it merely heard

**Found 2026-09-06, descent run turn 13, and NOT fixed.** `charter_observe`
delivers a beat's public conduct to every Charter body that sensed it, and
speech admitted at `full` lands as an ordinary `kind='news'` claim carrying
`exact_quote`, the speech acts, and a `figure` claim for the speaker. That is
right for a person: gossip, reporting lines, carrier projection and promotion
all know how to move a news claim, and a body that heard the words has the
words.

A CREATURE IS ON THE SAME RAIL. `charter_creature`'s carbonic stalker, one
room away through what its own side of the doorway called an open door, held
both characters' lines verbatim -- `claim_text`, `exact_quote`, `speech_acts`,
`provenance: witnessed_speech` -- and a figure claim for each speaker. The
owner's design statement for creature hearing is the opposite of that:
"doesn't need to parse what it hears at words. just needs to parse that it
heard something", which is what `hearing_for_creatures` builds (`overheard`,
`{room: rank}`, no words, no speaker, no content).

Two things are true at once, which is why this is a decision and not a bug:
the creature DID have a channel (a body with ears in the next room), so
nothing crossed a firewall; and a thing with no language holding a transcript
is wrong the moment the pipeline renders it "with full fidelity" at the
Director bubble, because it arrives carrying conversations it can only have
heard as noise.

**Not decidable from the engine's vocabulary as it stands.** "Creature" is one
flag (`state.creature`) covering everything from a stalker to a horror that
talks, and the distinction the rule needs is whether a mind has LANGUAGE, which
nothing on the charter says. The narrow reading -- a creature receives the
noise channel and not the speech channel -- would be wrong for the talking
horror; the wide reading -- every mind holds what it heard -- is what is built
and is wrong for the stalker.

**No longer live in the descent story**, because § 1.137's barrier repair drops
ordinary speech from the spine to the annex to `none`. The class stands.

**A second, smaller thing in the same rows:** a landed claim's `place` is the
WITNESS's room ("what this Charter person believes they saw at this place"),
so the stalker's figure claim puts both characters in the annex while they
stand in the spine. Nothing hunts by it -- `hunt_moves` reads `overheard` and
the sensed rooms, not `minds` -- so it costs nothing today, and it would cost
a great deal the first time something does read it.

<a id="unbuilt-1-141"></a>

### 1.141 A scent hunter that loses the trail stops instead of casting — BUILT 2026-09-06

**Built and measured 2026-09-06, and the missing half is named here.**
`world/spatial_scent_field.py` gives a body's trail memory: it accumulates
while somebody stands somewhere, bleeds one room per beat, decays by the
room's `exposure`, and is stopped almost dead by a shut door. A creature with
`senses.scent` reads the gradient over its neighbours and walks uphill.

**Measured on a five-room corridor, a body walking r0 to r4 at two beats a
room:** the trail reads 0.067 / 0.117 / 0.169 / 0.233 / 0.316 -- a clean
monotone line to the prey -- and it is gone by about beat 20. Pull the door
into r3 shut behind you and the hunter arriving at r2 reads `{r2: 0.169,
r1: 0.117, r3: 0.165}`: its own room is the local maximum, there is no uphill
step, and it has lost the trail.

**And then it stops, for ever, which inverts what the sense is for.** The
owner's reading of the mechanic is right -- a scent hunter should be slower
to notice and much harder to shake than a hearing one -- and without a search
behaviour it is the opposite: one shut door defeats it permanently, where a
hearing hunter would still come to the next noise.

**What the literature says to build** (`docs/guides/RESEARCH.md` § 1.8, and
it is the single most useful claim in it): CAST AND SURGE. Surge while the
odour is detected; when it is lost, cast across the neighbourhood with
widening amplitude until it is picked up again. Trained agents rediscover
this independently, and it is what makes the searching read as intelligent
rather than as a stall.

**The shape it wants here.** A creature that had a trail and no longer has an
uphill step remembers where it last had one, and probes outward from there --
neighbours first, then their neighbours -- for a bounded number of beats
before giving up and returning to its own business. Bounded, because a
creature that searches for ever is a creature that never lets a story move
on, and the bound is the thing to name.

**BUILT, the commit after.** `charter_predation.CAST_BEATS` (six) bounds it,
and `hunt_moves` gained the third way a creature notices: surge while the
trail is live, and when the pull names its OWN room -- the trail ends where
it stands -- step to the nearest room it has not already tried, widening,
until the bound runs out. Six beats because shutting one door should buy
distance rather than safety, and because a creature that searches for ever
is a creature that never lets a story move on.

**A NOSE CASTS AND AN EAR DOES NOT**, and the asymmetry is the point: a
noise is over the moment it happens, so a hearing creature has nothing to
have lost. That is what makes the scent sense the slow one to notice and the
hard one to shake, which is the shape the owner asked for.

**One flaw the tests found rather than the design.** The room a trail dies in
is a local maximum, so a creature that cast away from it was pulled straight
back the next beat and paced between two doorways for ever. A body's `tried`
list is now seeded with the room it was standing in and refused as a SURGE
target for as long as the cast lasts, so the search opens outward instead of
oscillating. The list is cleared the moment it surges to something new or
gives up, so a fresh trail laid in the same room is followed normally.

`casting` is declared in `normalize_charter` -- the fifth key this year that
would otherwise have been written by a round and normalized away unread.

<a id="unbuilt-1-142"></a>

### 1.142 An edge cost ten minutes because the courier said so

**Found and fixed 2026-09-06, playing the descent run.** The carbonic
stalker smelled the players at the top rung, named the right room, and
`hunt_moves` returned a walk into it -- and it never arrived, for four
beats and counting. Nothing in the creature path was wrong.

`charter_move.WALK_ROOMS_PER_HOUR` is 6: **600 seconds, ten minutes, to
cross one edge**, and its own note says why -- it is pinned equal to
`story.couriers.PACES["walking"]`, because "a townsperson on an errand walks
the same streets at the same speed". That is right for the courier it was
pinned to, whose edge is a road between two places. A SCENE's edge is a
doorway, and a 24-pace service spine is about eighteen seconds' walk.

**Measured, and my first number was wrong.** I reported 750,000 beats per
room; that came from one beat's rounding residual (405.9992 against 406.0)
and was nonsense. The scene clock is HEALTHY: the descent's beats declare 6
to 45 seconds each, 406 seconds across 20 turns. The true figure was about
30 beats to cross one room, in a story four minutes long. The owner named
the real fault in one line -- "ten minutes is still quite too long to cross
a single room" -- and it was never the clock.

**An edge now costs what the room IS** (`charter_move.edge_seconds`): the
room's own measured `extent` at a walking pace, plus what the edge's own
`distance` word is worth. Live: the descent's corridors are 10.8 and 12.3
seconds, a `far` road is 191.

**THE FIRST SCOPING WAS WRONG AND THE OWNER SAID SO TWICE.** It kept the ten
minutes wherever a room carried no `extent`, on the reasoning that a size
TIER is a guess rather than a measurement -- which protected a test fixture
rather than a truth. No room takes ten minutes to walk through, measured or
not, and the light and sound fields have read tiers as geometry all along, so
refusing to here was inconsistent as well as wrong. The span always decides
now: 2.3 s across a `tiny` room, 4.6 across a `medium`, 9.2 across a `vast`.
The old flat rate survives as a CEILING and as the answer for a scene holding
no rooms at all.

**What broke was fixtures, not physics, and that is the finding.** Fifteen
tests failed across traversal, couriers and caravans, and every one models a
ROAD as a bare edge -- a town's square-to-tavern, a keep-gate-road-square
courier run, a farm-lane-market-road-town caravan route. A bare edge is a
doorway once a crossing is priced from the room it crosses, so those streets
became six-second rooms and everybody teleported. They now declare
`distance: "far"`, which is the plan schema's own word for a way through
that takes more than one beat: a town street costs 189 s, about three
minutes between places, and the courier's road behaves as it always did.

The traversal tests were rewritten to express their INTENT rather than a
magic hour -- `_window_for(6)` derives a window that buys six legs from the
pace itself -- so "a body is caught in the last street before the door"
survives any later move of the constants, and being visible mid-journey
stays the thing being defended.

**The courier keeps its promise as a multiplier** (`couriers.COURIER_SLOWNESS`,
`COURIER_EDGE_FLOOR`), on the owner's ruling. Its flat rate was defending a
real verb -- "BOTH are slower than a walking player, who crosses a room in
one beat: outrunning a route is a verb the design promises the player" --
and a multiplier over the real crossing defends it better than a number that
ignores the room: 1.5x riding, 3x walking, floored at 45 seconds, which is a
beat at its longest. A measured corridor costs a courier 45s, a long road
554s, an unmeasured edge the old 600s. Never faster than a player.

**Still open, and it is the same class one tier up:** `predation_round`'s
`hours` and every upkeep drift are denominated per HOUR, so a creature's
hunger moves by 0.0002 across a four-minute scene. Nothing in this story
depended on it, and re-pricing appetite is not the same question as
re-pricing a doorway.

<a id="unbuilt-1-150"></a>

### 1.150 A creature has no held hunt — the courier maze problem, one subsystem over

**The owner's read, 2026-09-06, on watching a predator walk home past its
prey: "This is the courier maze problem all over again."** It is, and the
parallel is structural rather than poetic.

THE COURIER (`docs/experiments/MAZE_ARMS.md`, and CLAUDE.md's psychology
section) walked SIXTEEN OPTIMAL ROOMS to his destination and turned away,
because his motivation lived in `initial_state.goals` -- built to be
completable and abandonable -- and nothing underneath the spent goals
wanted it. Perfect navigation, no wanting on arrival.

THE CARBONIC STALKER (chat 117, turns 58-63) followed a CO2 gradient to
the exact room its prey stood in -- `smelled` reading 4.0 there against
3.0 either side -- stood in it for four beats emitting its `idle` voice,
and then turned for its berth while the cast were still in the next room
leaving a fresh trail. Perfect navigation, no wanting on arrival.

**MEASURED, AND THIS IS THE SHARP END.** Its want is the `hunger` upkeep,
which drifts per HOUR:

  * 63 turns of story = **0.2375 story hours** (fourteen minutes).
  * Hunger drift across the ENTIRE RUN: **0.0036**.
  * Hunger on turn 0: **0.7000**. Hunger at turn 63: **0.6964**.

To within a third of one percent it is exactly as hungry as it was when
the lift fell. Its motivation cannot move on any timescale a scene
reaches. (This is § 1.142's registered residual -- "predation_round's
window and every upkeep drift are per-HOUR" -- met from the other end and
now with a number attached.)

**THE COURIER'S ANSWER WAS A TIER, AND THE CREATURE IS MISSING THE SAME
ONE.** `projects` exist because a drive is eternal and PLACELESS (so it
cannot be walked to) while an intention is completable, abandonable and
swept when dormant (so it dies on a barren stretch). A project is durable
but not eternal, names a place, and BIASES appraisal rather than competing
in the beat auction -- and it is what made NPCs pass the maze with no
alteration to their drives.

A creature has exactly the two tiers the courier had and nothing between:

  * an UPKEEP that is eternal, placeless and, on a scene's clock,
    motionless -- the drive;
  * per-window moves from `hunt_moves`, re-derived from scratch every
    window and abandoned the moment anything else is in progress -- the
    intention.

**There is no HELD HUNT**: nothing that says "I am hunting these two,
still, across windows, and going to my berth does not outrank that." The
creature cannot be committed to anything. It can only be, at each window
independently, near something or not.

**WHAT SHIPPED TODAY IS THE INTERRUPT HALF, NOT THE HOLD HALF.**
`hunt_moves` skipped any body that was `en_route`, so a creature that had
given up and turned for home could not notice prey again until it arrived
-- it strolled past its dinner. Prey may now break into a walk (casting
still may not: re-opening a search every window is the dithering that
exclusion exists to stop, and `_dispatch` already held the rule -- "the
watch changed, and the body turns"). That stops the specific absurdity. It
does not give the thing a memory of what it wants.

**What the hold half would need**, if it is built: a per-body commitment
that survives a lost trail and a completed errand, names its quarry rather
than a room, decays on a scene-scale clock rather than an hourly one, and
outranks routine charter errands without competing with them -- which is
the project tier's contract almost word for word. Worth reading
`DESIGN_LONG_TERM_GOALS.md` and `affect.apply_project_ops` before
inventing a second mechanism for it.

<a id="unbuilt-1-152"></a>

### 1.152 A creature can be stopped by the shape of an opening and by nothing else

**Found by a player inventing a defence the engine had no word for**, chat
117 turn 72. The cast, cornered in a dead-end shaft with a deaf CO2 hunter,
worked out from the fiction that the spilled drums were the one thing it
would not walk through, drew a drum with standing solvent in it back
through the gap, and poured a continuous line across the sill.

**The Director recorded it FAITHFULLY.** `_11`'s anchors afterwards:

    ['lateral_doorway', 'pressure_door', 'wrecked_trolley',
     'spilled_drums', 'chemical_barrier']

plus a `substances` row. `chemical_barrier` is a durable named place: prose
can point at it, a body can stand at it, it survives the beat. Nothing
about the recording is wrong.

**AND NO CREATURE CAN BE STOPPED BY IT.** `charter_creature.creature_neighbors`
builds the graph a creature walks from `passable_neighbors` (edges), plus
shut doors where `can_open_doors`, minus rooms its `footprint` does not fit
-- and its own docstring names exactly the two constraints it models: "a
door that holds a wolf and a passage too narrow for a large thing". Both are
facts about the WAY THROUGH. An anchor on the floor is a third kind and
there is no field for it.

The whole vocabulary a creature charter can be consulted on:

    active_phases, bargains, boldness, can_open_doors, contest,
    encounter_odds, fed, footprint, hoard_holder, kill_ceiling, look,
    noun, prey, senses, spoor, stock_lots, take, voice

`can_open_doors` is the only movement constraint in it, and it is a single
hard-coded affordance rather than a general one. A creature cannot be
authored to avoid anything.

**WHY THIS IS THE INTERESTING SHAPE.** Every other defect on this path was
the engine holding a true thing in a form the next stage could not use. This
one is the opposite: the engine records the player's invention perfectly and
has no vocabulary to be affected by it. The scent model tracks what a
creature HUNTS and has no notion of what repels it; `SCENT_PASS` grades what
a barrier does to a smell passing through, never a smell that IS the
barrier.

**Where it belongs when built, in this engine's own idiom:** the obstacle is
a fact about the way through, which is where `barrier` and `material`
already live and what `creature_neighbors` already reads. A substance laid
across a threshold wants to reach the EDGE, not to become a second mover --
`charter_move._advance` re-checks every edge of a planned route against the
map it is handed and holds the body where the check fails, so an edge that
says "a nose will not cross this" needs no new machinery to be obeyed. The
creature side then wants one general field (what this thing will not cross)
rather than a second `can_open_doors`.

**Unmeasured across the corpus, and cannot be:** there are 0 creature
charters anywhere but this story (s1.151), so this has never had the chance
to be wrong before.

**CONFIRMED IN PLAY, turn 82.** The creature is now standing in `_11` --
the room whose anchors are `['lateral_doorway', 'pressure_door',
'wrecked_trolley', 'spilled_drums', 'chemical_barrier', ...]`. It walked
over the line. The barrier held for exactly as long as the Director was
resolving the confrontation beat by beat ("It did not cross.", turn 73) and
stopped meaning anything the moment the creature moved on its own schedule
through `hunt_moves`, which reads `creature_neighbors` and has no word for
what is on the floor.

So the two paths disagree about the same barrier: the one that runs when
the player is watching honours it, and the one that runs when they are not
does not. That is worse than a barrier nothing implements, because the
first path teaches the player a rule the second does not keep.

## 2. Roadmap

<a id="unbuilt-2-7"></a>

### 2.7 Reactivation negotiation

**The roadmap half of this entry was retired 2026-09-04**, with the tier split
that made charter the answer for bodies off screen and playerless causality
bubbles the answer for a major character's off-screen cognition. What went was
the build order: a reactivation proposal, and a negotiation protocol with
refusal budgets, integrity-only refusals, and the last proposal becoming canon
on exhaustion. Its proposer was the mapping agent, which is itself retired.
Argument, for the record:
[`OFFSCREEN_LIFE_DESIGN.md`](design/OFFSCREEN_LIFE_DESIGN.md).

Two things are kept here because nothing else records them.

**Steps 1–5 of the build order landed** (bg-life work, 2026-08): `gaps.gap_for`
plus the `subject_last_seen` ledger, the chat-level `offscreen_life` ceiling,
`offscreen.stochastic_ticks`, typed `reactive` plan stages, and
`offscreen.schedule_agent_ticks`. Step 2's per-character half landed as an
IMPORTANCE override (`simulation.offscreen_importance`, read by
`offscreen.importance_for`) rather than a per-character RUNG — deliberately: the
ladder answers what a character MAY do, importance answers how much they matter,
and one vocabulary answering both is the `flow.reactors` defect re-minted. The
rung opt-in that step 4 wanted now exists as `simulation.offscreen_agent`
(`world/offscreen.py`), so that residual is closed too.

**The negative result.** Verified 2026-08-19 and re-verified 2026-09-04:
`reactivation`, `negotiat` and `refusal_budget` return **zero** hits across
every non-test module. Nothing was ever built, so nothing has to be unbuilt.

Precedent that did not exist when the note was written: `world/background_claims.py`
is exactly the "commit invention as claims, not facts" mechanism its decision 3
asks for, built for background presences.

<a id="unbuilt-2-8"></a>

### 2.8 Richer off-screen life

Deterministic scheduling exists; what is missing is the world visibly having
moved while you were away. The costing argument this entry opened with — that
most of the cast needs no tick because the gap is generated at re-contact — was
retired 2026-09-04: charter moves an unwatched population continuously, so the
question is no longer whether to tick but what the ticks may know.

**Almost all of it has landed** and the record is in `CHANGELOG.md` and
`Design.md`: the `offscreen_life` ladder as a chat-level ceiling, a model-free
seeded `stochastic` rung, out-of-band profile ticks on a frame-scoped
`offscreen_epoch`, `world_events` as the objective spine (schema v27, with
checkpoint/archive/branch/migration), carrier delivery and couriers, caravans
and artifact carriers, and typed `reactive` plans that require a same-beat
declared basis. `character_agent` is marked built in the UI.

**One bullet is open, and it verifies.**

- **The stored `offscreen_log` history is still mixed** across four legacy
  shapes (`{actor, tick}`, `{event}`, `{who, event}`, `{description}` all appear
  in the same field across eight live chats) plus the new record shape.
  Nothing migrates what is already stored, and every reader coerces for itself. Cheap
  while nothing computes over the history, and a trap for the first thing that
  does.

**Direction changed 2026-08-21, and it reopens this entry.** The goal is now
*relatively high-fidelity off-screen simulation performed in code*, with model
calls reserved for the aperture (interpretation at contact, and promotion when
a background body becomes someone the player talks to). The premise this entry
was written under — that the deterministic spine is a cheap floor and fidelity
above it is bought with calls — was measured false: a per-turn sweep of 1,000
bodies × 100 belief facets is 193 ms in plain Python, 500,000 facets is 845 ms,
off the critical path against a ~22.5 s character call. Recorded at
`design/DESIGN_LIVING_WORLD.md` §8.1 and
`design/OFFSCREEN_WORLD_ARCHITECTURE.md` §1.1; the worked case is
`design/DESIGN_INSTITUTIONS_AND_UPKEEP.md` (deterministic vertical slice built).

What remains in this register:

- **The `offscreen_log` migration above still blocks any consumer of that
  legacy history, but no longer blocks Charter's current-state slice.** Charter
  owns a new typed, frame-scoped registry and writes incidents through
  `scheduled_events` -> `world_events`; it never reads `offscreen_log`.
  Backfilling Charter history from older play, or building any cross-system
  retrospective over the legacy log, must migrate the four shapes first.
- **Institutions and upkeep — deeper realism and product authoring.** The five
  genre-neutral primitives, pure simulator, frame-scoped epoch job, guarded
  persistence, consequence mint, destination aftermath and per-presence slice
  are built. The current `/api/chats/{cid}/charters` surface is structured but
  raw. Still open: upkeep readings as beliefs rather than ground truth,
  fractional labor/service, travel and handover time, body refusal/projects,
  recovery-place requirements, nested charters, adaptive safe ensemble
  batching for Charter people, and a
  guided authoring UI with templates. Deliberately NOT called `stations`:
  that word already means a body's within-room position.
- **Typed belief facets for what travels off screen.** Contradiction over
  prose is semantic, which is why deterministic dispute detection was refuted;
  over `(owner, subject, facet_type, value)` it is a key comparison. Scope it
  to a small closed vocabulary whose values are REFERENCES (entity, room,
  `event_id`) rather than strings — a reference needs no hand-authored
  mutation graph, which is the tuning burden that measurably hurt the one
  published system at this scale. Facets must be a derived index over
  `world_events`, never a parallel store; the precedent is
  `composer.observations_from_render`, where the second representation is
  re-derived so it cannot expand the information budget.
- **Two rules the extra fidelity must not be allowed to break**, stated here
  because they are cheap to lose: storage grows with *incident* rather than
  time (recompute from the clock at contact, commit only branches —
  `world/routines.py` is the standard), and the world never forgets while
  minds do (the objective spine is monotonic; culling unreachable facts makes
  the world observer-relative).

<a id="unbuilt-2-29"></a>

### 2.29 Who the player talks to — residuals

**Found:** the Harrowmere playtest (2026-09-02), landed 2026-09-03 as
`tests/test_who_you_talk_to.py`; what the fix deliberately left.

- **Title words are derived per story, not per room.** `_shared_name_words`
  reads every tracked name in the ledger, so a story with one reeve in the
  hall and one in a distant town shares "reeve" between them and the loose
  match reaches neither; the flow refs, the descriptor binder and the exact
  name still do. Measured on nothing yet.
- **The Director learns of a proposed promotion one beat late** — the
  engine channel is read next beat by design — and the owner sees it as a
  turn warning plus the presences panel's `promotable` badge; there is no
  chat-level notice.
- **Leave at a threshold is a clause, not a fact.** Nothing records that a
  resident said yes; the next beat's Director reads the resident's line in
  the dialogue log like any other. A knock at an EMPTY home is answered by
  the clause ("a door unanswered stays a door") and by nothing else.
- **A legacy lower-case name is healed at render, not in the registry.**
  `heal_name_case` runs in `display_name`, and only for a body carrying the
  `given_name`/`family_name` components a law stores beside a name it
  built; a reader that takes `body["name"]` raw still sees the stored
  spelling, and a generated body from before those fields existed is not
  healed at all. `_body_refs` compares casefolded, so resolution is
  unaffected.

**Replay residuals (2026-09-03, `tests/test_replay_defects_h.py`):**

- **A role noun the post's noun neither equals nor ends is not bound.**
  The identity floor matches a minted role by head noun, or by a compound
  ending in the post's noun (a blacksmith is a smith); "the hostler" beside
  a stablehand and "the brewer" beside a cook are the same person in the
  charter's own authority text and the floor does not read it. Measured on
  the replay's seven mints against the final registry (ambient shadows
  excluded): the arrival-room fix plus the compound rule reach the ones
  whose post noun is a head or a tail of the minted noun; the rest wait
  on the authority-text resolver (§1.103's target rule, fork I).
- **The measure above is against the post-run registry.** A body's place
  at turn N is not stored; the seven mints were re-bound against where the
  bodies stand at turn 39, which is right for posted bodies and a guess
  for the rest.
- **Chatter names an unmet SUBJECT by design** (`subject_label`: the name
  was said aloud, which is how a name first reaches you); only the
  speaker and the addressee now follow the observer's recognition. A
  subject named by chatter still does not enter the observer's `known`
  ledger, so the next fragment renders them anonymous again.
- **The threshold rule is one hop.** A player speaking at the door of a
  house they have declared a move into addresses the bodies inside; a
  player speaking at a door with NO declared move and no resolvable target
  addresses nobody, as before. Whether a knock without words is a demand
  is not modelled: a knock is an act, and only a line is aimed.
- **The narrator's invented-reply tripwire still reports and does not
  remove.** The unanswered-line clause states the class on the card; the
  measurement of whether it held is the next replay's invented-dialogue
  count (5 on 40 beats before it).

<a id="unbuilt-2-31"></a>

### 2.31 A townsperson's surface — residuals

**Landed 2026-09-03** (`world/charter_surface.py`, Design.md "A townsperson
has a surface"). What it deliberately does not do:

- **The replay's town wears the engine's face.** The Harrowmere plan in
  `tests/data/harrowmere_plan.json` was written before the look law
  existed, so every body there deals from the six-value default pools and
  the closure warns; a hundred bodies over six values an axis repeat.
  Measured on the replay registry: 27 bodies met, all 27 from the default.
  The next generated town is the first measurement of an authored law.
- **Worn does not come off.** A post's `worn` is its holders' working
  dress and rides the body all day and night; a smith asleep in a cottage
  is still "in a leather apron" to a silhouette. Tying `worn` to the
  body's phase (at post / off duty) is the obvious next step and was not
  asked for.
- **A render is refused on a phrase match.** `settle_render` refuses a
  Director render that names another value of an axis's pool than the one
  dealt, by word-boundary phrase; a pool value that is also an ordinary
  word ("short" in "short sword") refuses a render that contradicts
  nothing. The refusal is a warning and the entity keeps its description,
  so the cost is one unsettled render.
- **A silhouette descriptor is a memory entity.** `generic_labels` keeps
  the fixed dim-figure label out of memory; a composed silhouette ("the
  tall broad-shouldered figure in an apron") is not in that set and is
  indexed like any stranger descriptor. Deliberate -- it is a real thing
  the observer saw -- but it is a change to what a dim room leaves in a
  mind, and unmeasured.
- **The default pool is English-shaped.** `DEFAULT_LOOKS` in the ja pack
  is a translation of the en pool, not a Japanese look law; the compositor
  templates order adjectives for the language, and that is all.
- **`surface.gait` is dealt and never rendered in a label** (it rides
  `appearance_text` and the widening words only); a limp is the kind of
  thing a silhouette shows and could join the silhouette tier.

<a id="unbuilt-2-32"></a>

### 2.32 Creatures as charter — residuals (2026-09-03)

Landed as `docs/design/DESIGN_CREATURES_AS_CHARTER.md`. What it deliberately
does not do, and what the measurement left open:

- **Figures are never prey off screen.** `figure` is a prey category so a
  creature may notice the player or a major character, and the round does
  nothing about it: their fate is the causality bubble's. A creature that
  meets the player in play is the Director's to render from the same state.
- **No tactics.** Stalking, ambush and defending a lair against a hunt are
  character-frame work; off screen a creature is needs and routes.
- **A creature does not hunt the watch that hunts it.** A called watch at a
  place changes the contest there and can hurt an attacker; nothing walks the
  watch to the lair. A hunt is a post with a destination and is not built.
- **Spoor stands in play until the Director removes it or the next landing
  takes it down.** The registry's `until_hours` sweeps the record; the
  artifact follows on the next `land_snapshot`, so a beat between may show a
  carcass the town has already forgotten.
- **News reaches an office only through channels**, which is correct and is
  why a month of the small-town fixture shows one mobilisation in three arms:
  a posted herder who never leaves the pen never tells the reeve. The fixture's
  crew of three carries the news in the social phases; a town whose offices
  never meet its posts does not mobilise.
- **Between-creature predation** is allowed by the class and untested.
- **The last window's kills are reported at the next.** Events are carried
  and returned by the institution that lives through them, so a run's final
  window can end with a body dead and its `harm_done` not yet in the returned
  list (measured: big_town 48h, 2 gone, 1 reported). The state is right; the
  event arrives on the next window or catch-up.
- **The stepper's own overhead** on a thousand-body town is the difference
  between the two `alone` rows in the note's §10 (about four per cent over
  `run`, same events); a creature costs about nine per cent over `run`
  alone, flat in the number of creatures. The owner's bound was "no more
  than the creature's own bodies explain", and four bodies in a thousand
  explain half a per cent: the number is named in §10 rather than absorbed,
  and the round's company index, senses walk and spoor read are where the
  rest goes.
- **Cost bound.** A deep copy per kill was most of the round's cost on
  `big_town` and was removed (`apply_harm(copy_state=False)`); re-measure
  after any change to the round with `tests/charter_worlds.big_town`.

## 6. Design-note residuals

<a id="unbuilt-6-1"></a>

### 6.1 Background life — [`BACKGROUND_LIFE_DESIGN.md`](design/BACKGROUND_LIFE_DESIGN.md)

**The digest lifecycle (§3.5) was retired 2026-09-04** with the tier split. It
was a bespoke compaction of what an unwatched presence had been doing —
`digest`, compaction, freeze-while-unobserved, prune, `last_seen_clock` — and
charter now moves an unwatched population outright while the planned playerless
bubbles will give a major character the ordinary memory path. Only the raw
`recent` ring buffer was ever built (`BACKGROUND_RECENT_TAIL = 4`), and that
stays: it is what a presence's own reaction reads.

Most of the rest of §3 shipped in alpha 4.0. What did not:

- **Promotion conversion (§3.6)** — `importers.draft_promoted_character` reads
  the `events` table's `dialogue_log` and event text through
  `_promotion_evidence`, never `blurb` or `recent`, so a promoted presence
  loses the ledger the engine had been keeping about it and is rebuilt from
  the objective record instead (which is also §1.8's leak). The threshold half
  of this is closed by a different counter than the one proposed: promotion is
  gated on `addressed_turns` (`commit._promote_after_addressed`), which counts
  only DELIBERATE interaction — the Director marking a presence as the
  player's addressee, or the player naming them. `AUTO_PROMOTE_DIALOGUE_THRESHOLD
  = 3` still counts manager conduct, but it no longer decides, so an
  `ambient_turns` counter is no longer the thing wanted.
- **Interim filler on return (§3.9)** — no `interim` field, no `last_seen_clock`.
- **Canon-referenced blurbs (§3.8.1)** — no `canon_ref` field; substituted by a
  style-guide-level canon licence.
- **The separation eval (§3.3.1)** — the deterministic leak floor is built; the
  proposed measurement of real cross-presence leak rate has no artifact in-tree.
- **Location-themed population and the chorus presence (§4).** Not built and now
  with no artifact at all: `AggregateEntity` was declared in `llm/schemas.py`
  and consumed by nothing, and was deleted rather than wired. The design has
  neither an implementation nor a schema to point at.
- **The narrator dilution clause (§5)** — no tension-gated ambient suppression.
- **The `digest`/`interim` tier typology (§3.1)** — only `blurb` was built.
- **The prompt fix for §3.8** — a blurb tell should be available colour, not a
  required beat.

<a id="unbuilt-6-8"></a>

### 6.8 Living world — [`DESIGN_LIVING_WORLD.md`](design/DESIGN_LIVING_WORLD.md)

Phase 1 (branch `living-floors`) built the deterministic floors of A
(`world/routines.py`), B (`living_world.mint_consequences` +
`mechanics._fire_due_events`) and D (`place_obligations` +
`attach_owed_history`), plus the settings ladder for all five approaches
(`LIVING_WORLD_BUILT` is the declared/built authority). Held for phase 2,
which starts when the epistemic-leak audit branch merges:

- **C, the rumor ledger floor** — deliberately NOT the document's §3
  delay-line as written: the author's constraints (design doc §9, verbatim)
  require **carriers with positions and routes** the player can intercept,
  the anti-protagonist priority rule (propagation interest computed from the
  event, reputation downstream of delivery, the null result as the
  load-bearing test), and invented gossip entering through
  `background_claims` + the provisional tier as its first real producer
  (the lane measured 0-of-29). *Carriers with positions and routes have
  since landed as `story/couriers.py` (positions on `passable_path` routes,
  clock-driven movement, interception/silencing that stops delivery); the
  claims-lane producer and reputation rules remain as stated.*
- ~~**E, the antagonist ladder** — rungs 1 and 3 per §5; waits on C because a
  race lost without an information trail reads as the engine cheating.~~ —
  landed: the reactive floor fires authored stages, and the adaptive ceiling
  (`offscreen.schedule_agent_ticks`) adapts only from character-owned carrier
  evidence, C's trail having landed first.
- **The ceilings of A, B, D** — ensemble tick, consequence chaining
  (needs a significance flag *computed from event properties*, never the
  subject — §9.3), obligation-aware pre-generation. All documented as
  extension points only; `LIVING_WORLD_BUILT` marks these three unbuilt and
  `effective_depth` runs a requested ceiling as the floor. When one lands,
  it lands behind the rung `LIVING_WORLD_REQUIRES` already declares
  (`stochastic` for the A-D ceilings, `character_agent` for both depths of
  E): the off-screen ladder is the one authority ceiling, and a mechanism
  must never acquire authority the ladder did not grant.
- **Obligation retirement at honour time** — `attach_owed_history` still
  annotates a place's lore hits after the place has been generated (accrual
  stops structurally; attachment does not), and nothing yet marks a debt
  honoured. Harmless while obligations are rare; close it before C makes
  places chatty.
