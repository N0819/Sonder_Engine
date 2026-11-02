# The Living World

What happens when nobody is looking. Every claim here is against source — the
forty-one `world/charter_*.py` modules, `agents/offscreen_beat.py` with the
spatial bubble code, `world/living_world.py`, `world/offscreen.py`,
`agents/background.py` with `persist/commit_background.py`, and
`story/scene.py`'s `dialogue_config` and `background_config`.

**The paid off-screen tiers were retired on 2026-11-01.** The owner: "living
world is supposed to be superseded by charter and writers room." This guide
used to state a switchboard: a four-approach living-world ladder
(`off`/`floor`/`ceiling` per approach), the five-rung `offscreen_life`
authority ceiling over it, an actor cap, and three paid tiers that spent at
those rungs — a seeded `stochastic` tick draw, out-of-band `profile` ticks, the
`character_agent` rung, plus the antagonist ladder's `reactive` plans. None of
it could run after 7140b9cc (2026-09-20), when the approach list was emptied and
`dialogue_config` forced the actor cap to 0, and the owner's database never
stored a batch from any of them (review 2026-11-01, `world_offscreen_time` F11).
It is deleted rather than left switched off: about 2,100 lines of
`world/offscreen.py`, the ladder in `world/living_world.py` and
`story/scene.py`, the `/api/chats/{id}/living_world` routes, three prompts per
language pack and the card's `simulation.offscreen_agent` opt-in.
`tests/test_the_living_world_tiers_are_gone.py` pins that no engine module
binds a retired name again.

**What does their work.** The Charter moves an unwatched population every beat,
deterministically and without a model call (§3). The Writers' Room plans what
happens out of view and reaches into the Charter to make it so
(`agents/story_planner.py`, `story/plot_packages.py`, `world/charter_ops.py`). A
character who walks out of reach lives a causality bubble: a frame of their
own, their own perception, a real character call from their own private state,
and a Director that resolves it (`agents/offscreen_beat.py`,
`docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md`). And four floors run in every
story with no setting over them: consequence fuses fire on the story clock
(`living_world.mint_consequences`, `mechanics._fire_due_events`), an unvisited
place accrues the history it owes (`record_obligations`, `attach_owed_history`),
a room re-entered shows what changed (`routines.residue_for`), and the carriers
move what was witnessed body to body (`story/carriers.py`,
`story/couriers.py`, `story/artifacts.py`).

**What is left of `world/offscreen.py`** is the off-screen EPOCH: every beat
`advance_epoch` stamps a stable beat identity on the frame's `offscreen_epoch`
row — the token the Charter advances on and is idempotent against — and when a
beat crosses a boundary (`epoch_reasons`: the opening, a change of top-level
location, a crossed in-world hour, a due event) it records an epoch beside it.

Related: [`design/DESIGN_OFFSCREEN_SUPERSEDED.md`](../design/DESIGN_OFFSCREEN_SUPERSEDED.md)
for why the tiers went, [`design/DESIGN_LIVING_WORLD.md`](../design/DESIGN_LIVING_WORLD.md),
[`design/OFFSCREEN_LIFE_DESIGN.md`](../design/OFFSCREEN_LIFE_DESIGN.md) and
[`design/BACKGROUND_LIFE_DESIGN.md`](../design/BACKGROUND_LIFE_DESIGN.md) for the
arguments; [`EXTENSIONS.md`](EXTENSIONS.md) for the integration boundary;
[`DATABASE.md`](DATABASE.md) for the schema-change checklist.

---

## 0. Four names

The single largest barrier to reading this subsystem is that four different
things are named as though they were tiers of one thing. They are not. They
share no setting, no pipeline step and no ledger.

| Name | What it is | What it is **not** |
|---|---|---|
| **Charter** | The institution simulator: people, duties, upkeeps, beliefs, goods, reporting lines. Forty-one `world/charter_*.py` modules behind `world/charter.py`. A *thing that runs*. | Not a setting. Nothing named `charter` turns Charter on. |
| **Living World** | The deterministic floors that make the world keep its own causes: consequence fuses (B) and places that owe a history (D) in `world/living_world.py`, routine and residue (A) in `world/routines.py`, the carriers (C). | Not a switchboard any more. Its approach ladder was emptied 2026-09-20 and deleted 2026-11-01; every floor runs in every story. |
| **off-screen life** | What an ABSENT registered character does: a causality bubble of their own, opened when they walk out of reach (`max_bubbles`, `bubble_radius`). `agents/offscreen_beat.py`, `world/spatial_bubbles.py`. | Not a ladder. The five-rung `offscreen_life` ceiling and its paid tiers were deleted 2026-11-01. |
| **background life** | Voicing unregistered people who are **present in the room**, during the turn. `agents/background.py`. | Not off-screen anything. Its subjects are on screen. |

**The boundary sentence, if you remember one thing.** Background life voices
bodies that are PRESENT IN THE SCENE and UNREGISTERED (no `chat_chars` row,
tracked only in `background_presences`), during the turn, inside the
`background_react` step. Off-screen life advances bodies that are ABSENT FROM
THE SCENE and REGISTERED, in a frame of their own, one beat of theirs per
committed beat of the player's, out of band (`schedule_offscreen_beats`). A
townsperson nobody promoted is neither: the Charter moves them.
(`persist/commit_background.py`'s `track_background_presences`,
`agents/offscreen_beat.py`'s `live_bubbles`.)

### Other collisions worth knowing before you grep

| Term | Here it means | Elsewhere it means |
|---|---|---|
| `place_obligations` | the **world-KV key** of approach D's ledger (`OBLIGATION_KEY`, `world/living_world.py`) — what an unvisited place owes | not the Director's debt ledger, `pending_obligations`, deleted 2026-11-01; and no longer an approach key, since the ladder went |
| `post` | a Charter duty slot | `scene.stations` is a body's within-room position; the model docstring names this the one naming trap (`world/charter_model.py`'s module docstring) |
| `registry` | the frame-scoped `charters` KV blob | `room_registry` is the cross-frame room-identity ledger |
| `route` | a character-history topology decision (`story/history_routing.py`) | a spatial edge in `world/spatial.py` |
| `structure` | a planted, prose-free town skeleton in `world/structure.py`, composed into the live scene on demand | not a Charter primitive; it holds rooms, not people |
| `gap` | "what changed about subject X between turn N and now" (`world/gaps.py`), model-free | not an off-screen tick; it *reads* `offscreen_log`, it does not write it |
| `epoch` | a boundary the world crossed, recorded beside the beat stamp on `offscreen_epoch` | not a turn, and since 2026-11-01 not a spend gate: nothing is scheduled off it |

---

## 1. Every setting

Five, and none of them can switch the world's own causes off.

| Setting | Values | Default | Stored | Set by | Unreadable value |
|---|---|---|---|---|---|
| `max_bubbles` | `0`–`12` | `3` | `dialogue_config`, chat-global | the Dialogue Config panel's Absent threads card | the default (`story/scene.py`, `dialogue_config`); a stored `max_offscreen_actors` from before 2026-09-20 is read as this |
| `bubble_radius` | `1`–`12` rooms walked | `3` | as above | as above | the default, never the floor (`story/scene.py`, `normalize_bubble_radius`) |
| `background_config.scene_life` | `off`, `ambient`, `full` | `off` | world KV `background_config` | `PUT .../background_config` | treated as `off`, silently — there is no `normalize_scene_life` |
| `background_config.max_reactors` | `1`–`3` | `1` | as above | as above | clamped in the stage, not in the config reader |
| `background_config.max_managed` | `1`–`8` | `6` | as above | as above | clamped only on the HTTP route (`web/app.py`'s `bg_cfg_put`) |

**`max_bubbles` caps how many threads EXIST, never how many advance.** At the
cap the next character to walk away simply does not get a thread, and the
refusal is reported; an open thread is never paused to make room
(`agents/offscreen_beat.OFFSCREEN_BEATS_ARE_UNCAPPED`, the owner's ruling of
2026-09-17). `0` means none.

**Retired, and dropped where met.** `offscreen_life`, `offscreen_cognition` and
`max_offscreen_actors` in `dialogue_config` (`scene.RETIRED_DIALOGUE_KEYS`:
`dialogue_config` reports none of them and the panel's PUT stores none of them
again), the `living_world` world-KV row (read and written by nothing; kept
classified as a hand-set dial so a rewind leaves an old story's row alone), and
the card's `simulation.offscreen_agent` and `simulation.offscreen_importance`
(read by nothing; an old card keeps the keys).

---

## 2. "I want X to happen"

| Goal | What it takes |
|---|---|
| Nothing at all off screen | Not available, by design. The Charter, the fuses, the place ledger, the residue and the carriers are how the world works rather than features; `max_bubbles = 0` stops new threads for absent characters; it and `bubble_radius` are the only off-screen dials. |
| A consequence fired later from an adjudicated declaration | nothing — every declared fuse is minted and fires on its clock. A notice reaches the page only when the player stands where it fires (`mechanics._fire_due_events`); otherwise it is met at re-entry (`routines.residue_for`) or carried by a body that was there. |
| A place carrying its owed history into a scene | nothing — `record_obligations` accrues it as fuses fire and `attach_owed_history` hands it to the place's generation alone, never to a mind. |
| A room showing what changed while it was unwatched | a declared movement into a room seen before. Charter incidents reach the same payload slot and are prepended ahead of routine texture (`agents/director.py`, the `destination_residue` block of `director_resolve`). |
| A named absent character advancing their **own** plans | a causality bubble: the character walks more than `bubble_radius` rooms from the party and out of the building the party stands in, while fewer than `max_bubbles` threads are open. Their beats run out of band, one per committed beat of the player's, from their own perception and private state (`agents/offscreen_beat.py`). |
| An authored antagonist advancing a plan unwatched | the Writers' Room plans it — plot packages, scheduled events and Charter operations (`story/plot_packages.py`, `world/charter_ops.py`) — or the antagonist is a character, and lives a bubble. |
| An institution **catching up** — its people, duties, markets and gossip advancing over elapsed time | A charter in the registry, and nothing else. Ungated since 2026-09-04: charter is where an unwatched body lives, and its advance path spends no model call. |
| An unregistered presence speaking in the room | `background_react`, gated only by `pick_background_reactors` and `max_reactors` |
| A creature hunting a town off screen — kills, raids, spoor, tribute, and the watch called out | A charter carrying `creature` in the registry (ungated, as above) (`world/charter_creature.py`); the catch-up then steps every charter TOGETHER with a predation round between windows (`world/charter_predation.run_registry`, `charter_runtime.advance_snapshot`'s together arm). A registry with no creature never enters that arm. The town answers through `charter_decide.mobilisation_calls` when a post with `mobilise` authority holds a threat claim above its credence |
| A whole location's populace voiced in one call | `background_config.scene_life = ambient` or `full` |

An **epoch** is one frame-scoped boundary the world crossed, recorded at most
once per beat when `epoch_reasons()` is non-empty, with one `epoch_id`
(`world/offscreen.py`, `epoch_reasons`). It is not a turn — many turns of
conversation can pass inside one epoch. Since 2026-11-01 nothing spends on it:
the Charter advances on the BEAT stamped beside it, every beat.

---

## 3. Charter, in five nouns

Enough vocabulary to read any `charter_*` module. All in
`world/charter_model.py` unless noted.

| Noun | What it is |
|---|---|
| **upkeep** | A condition the institution owes, held at or above a `floor`, drifting down at `drift_per_hour` unattended and back up at `service_per_hour` when a competent body tends it. `normalize_upkeep` |
| **post** | A duty slot: a place, a competence requirement, the upkeeps it `serves`, an optional `reports_to` line, a closed `authority` list. `normalize_post` |
| **competence** | `{tag: level}` on a body, author-owned tags. `meets()` is satisfied only when every requested tag is present at or above its level. `_tags`, `meets` |
| **watch** | `{post_key: body_key}` for one planning window — who the institution *tried* to put where. Produced by `plan_watch` (`world/charter_plan.py`), carried on the charter by `normalize_charter` so role continuity survives persistence |
| **charter** | One institution: upkeeps, posts, bodies, the roster it believes it has, its `priority` ordering of what it abandons last, plus every layered store. `normalize_charter` |

Three more you cannot proceed without:

- **body** — a person the charter may assign. `key` (durable institutional id)
  is separate from `name` (scene-facing identity). `available` is **ground
  truth**. `normalize_body`
- **roster** — what the charter *believes* about its people, with its own
  competence and availability claims, improving on observation and decaying
  otherwise (`world/charter_roster.py`). The planner never reads `bodies`; it
  reads the roster. That gap is deliberate and is where institutional error
  comes from.
- **figure** — a person the institution can know without owning: the player, a
  major character. Never rostered, never planned, never blamed, holds no mind
  inside the charter (`world/charter_figure.py`, `normalize_figures`).

### The module map

Forty-one files, seven themes. The count is `ls world/charter_*.py`, not this
table's length: a module added without a row here is the drift this section has
already had once.

| Theme | Modules |
|---|---|
| **Shape** | `charter_model` (the primitives), `charter_identity`, `charter_space`, `charter_place` (within-room standing, derived at read time) |
| **People** | `charter_needs`, `charter_temper`, `charter_feel`, `charter_move`, `charter_figure`, `charter_promote`, `charter_enrol` (the fill behind an unplanned body), `charter_harm`, `charter_mark` (temporary social facts), `charter_surface` (what a body looks like) |
| **Belief** | `charter_mind`, `charter_roster`, `charter_talk` (gossip), `charter_news`, `charter_social`, `charter_politics`, `charter_observe` |
| **Presentation** | `charter_chatter` (what a room sounds like), `charter_crowd` (people at rest as one crowd) |
| **Doing** | `charter_plan` (staffing), `charter_practice` (situations and affordances), `charter_decide` (agendas and orders), `charter_commitment`, `charter_author`, `charter_intervene`, `charter_trigger` (rules that fire off a change), `charter_ops` (what an authored event may say), `charter_surgery` (the Writers' Room nudge toolkit) |
| **Material** | `charter_economy`, `charter_drift`, `charter_creature`, `charter_predation` (the round between institutions) |
| **Time and I/O** | `charter_run` (advance a window), `charter_runtime` (the production seam), `charter_generate`, `charter_history`, `charter_log` |

**`world/charter.py` is an internal facade, not the public API.** Twelve
siblings are structurally outside it and must be imported directly by engine
code — `charter_creature`, `charter_crowd`, `charter_enrol`,
`charter_generate`, `charter_harm`, `charter_history`, `charter_observe`,
`charter_ops`, `charter_predation`, `charter_runtime`, `charter_surface`,
`charter_surgery`. Its docstring enumerates the seam for twelve of the
forty-one and says so; treat that as the first split's framing, not coverage.
(E33, 2026-09-07: this said four siblings and ten of twenty-nine.) And unlike `world.spatial`,
`agents.director`, `persist.commit` and `mind.memory`, this facade is **not**
machine-enforced — `tools/project_check.py`'s `FACADE_FAMILIES` does not list
it. Direct sibling imports work. That is not permission.

---

## 4. Storage

| What | Where | Frame-scoped |
|---|---|---|
| absent-thread dials (`max_bubbles`, `bubble_radius`) | `dialogue_config` | no (chat-global) |
| Charter registry | world KV `charters` | **yes** |
| place-obligation ledger (approach D) | world KV `place_obligations` | **no** — chat-global across every era |
| planted town skeletons | world KV `structures` (`world/structure.py`) | **no** — chat-global |
| off-screen epoch and beat stamp | world KV `offscreen_epoch`, per frame | **yes** |
| `offscreen_log` — the append-only tick ledger (bubbles append; old stories hold retired-tier batches `world/gaps.py` still reads) | world KV, per frame | **yes** |
| the retired ladder's rows, read by nothing: `living_world`, an old story's `offscreen_plans` | world KV | `offscreen_plans` **yes**, `living_world` no |
| background presences | world KV `background_presences` | **yes** |
| fired consequences, Charter incidents | `scheduled_events` → `world_events` | rows carry `frame_id` |

`charters` being frame-scoped has a sharp edge: a bare `wget(cid, "charters")`
reads a *different row* than `registry_for(cid, frame_id)` whenever a frame is
active — the key on disk becomes `charters\x1efr<frame_id>`
(`core/db.py`, `_FRAME_KEY_SEP`). Always go through `registry_for` /
`save_registry`.

`registry_for` also normalizes on read, so a round trip is **lossy** for any
field `normalize_charter` / `normalize_registry` does not enumerate. Adding a
persistent charter field means adding it to `normalize_charter`, or it will not
survive one read. `normalize_registry` silently discards any `recent_events`
key it finds (`world/charter_runtime.py`, `normalize_registry`); incidents
belong on `scheduled_events`.

### Lifecycle

**Carried, by construction.** All of this state lives in `world` KV plus
`world_events` / `relationship_events` / `scheduled_events` / `room_registry`,
and every one of those is in both `chat_archive.WORLD_TABLES` and
`checkpoints.snapshot_state`. So checkpoint, rewind, branch, archive
export/import and clone carry it with no Charter-specific code path, and story
delete removes it (`persist/chat_delete.py`). The three *settings* are
additionally in `checkpoints.PRESERVED_SETTING_KEYS`, so a restore keeps the
configuration and rolls back only what it caused.

Adding a persistent Charter field is therefore free on those paths — provided
it goes in world KV or one of those tables, **and** is enumerated in
`normalize_charter`. A new table is not free; follow
[`DATABASE.md`](DATABASE.md)'s checklist.

**Not carried, and this is the sharp edge.** Spatial frames are a different
mechanism from the five above, and Charter does not cross them:

- A frame **split** seeds the away frame from eight parent keys —
  `known`, `simulation_clock`, `standing_intentions`, `shadow_profile`,
  `background_presences`, `offscreen_log`, `charter_last_places` and
  `knowledge_circles` — plus each cast member's `relationships:<id>`
  (`world/spatial_frames.py`, `perform_split`). `charters`, `offscreen_epoch`
  and `offscreen_plans` are **not** among them; the registry is the era's,
  shared rather than copied.
- A frame **merge** reconciles only `simulation_clock`, `known`,
  `relationships:<id>` and `scene` (`world/spatial_frames.py`,
  `perform_merge`), with knowledge circles unioned back. Nothing a standing
  intention did in the away frame comes back; those rows are orphaned.
- `create_frame` writes no world rows at all (`core/frames.py`), so a newly
  created past/future/other era has no `charters` row and every catch-up tick
  there records `charter_skip: "no_charters"` until one is generated.

**None of the carried behaviour is tested.** No test in the suite covers
Charter, Living World or off-screen state across archive, branch or checkpoint
— the coverage is inferred from the table lists, not demonstrated. Treat the
first paragraph as a reading of the mechanism, not as a guarantee.

---

## 5. What an integrator can call today

| Route | Does |
|---|---|
| `GET/PUT /api/chats/{id}/charters` | read/write the frame-scoped registry |
| `GET /api/chats/{id}/charters/diagnostics` | inspect belief, judgment and planning state; `?body=` selects one body |
| `POST /api/chats/{id}/charters/generate` | generate one lore-grounded lived location; the body's `population` (an integer) is a closure input the closer lands within `POPULATION_TOLERANCE`, and the result's `closure` record says what was asked, planned and closed, which head posts were held to one holder, and which berths were split |

The three `charters` routes take a `frame_id` query parameter, and the
mutating ones call `_require_frame_idle` first — a turn in flight refuses a
Charter write with a 409. (`GET`/`PUT /living_world` sat beside them until
2026-11-01; it went with the ladder it set, and an old caller gets a 404.)
`GET /charters` returns the registry plus `character_history_routes`,
`character_journey_histories` and `registry_warnings`; `GET
/charters/diagnostics` returns beliefs, judgments, provenance, obligations and
decisions, and `?body=` unlocks the per-body belief fields. Those two are the
Charter read surfaces; `story_view` and `/world` are generic fallbacks that do
not carry this state at all.

`registry_warnings` is not advice — it has a behavioural consequence. Two
Charter bodies resolving to the same display name means scene presence is
WITHHELD, and `apply_presence_conduct` refuses with
`ambiguous_charter_identity`.

### From Python

Three hooks, one behind a capability name. Importing `world.charter_runtime`
directly is still outside the boundary; these are the supported path.

| Surface | Capability | Does |
|---|---|---|
| `story_view(...)["living_world"]` | none — the key is always present | `max_bubbles`, the background config, a row per institution, and `registry_warnings` (schema 5; schema 4 carried the retired ladder here instead) |
| `story_view(..., charters="full")` | as above | the complete registry — the same bytes `GET /charters` serves |
| `api.generate_lived_location(...)` / `api.living_world_job(...)` | `living_world_generation` | add an inhabited place, and see whether a previous attempt was interrupted |

**`provision_story(..., offscreen_life=, living_world=)` is retired, and
accepted.** Its capability name `living_world_provisioning` left
`api.capabilities` on 2026-11-01 with the ladder the two arguments set. `ext_api`
stays 1, so every rung, approach and depth either argument ever accepted is
still accepted, provisions nothing, and is reported three ways: a
`DeprecationWarning`, a line on the extension's log, and a sentence in the
result's `deprecations`. A value the ladder never had is still refused before
the archive is touched (`extension_runtime/api.py`,
`RETIRED_LIVING_WORLD_APPROACHES`).

A lived-location request may name characters by `resource_uid` — the identity
that survives an archive — instead of by this install's row ids, which is what
a caller that has just provisioned a story actually holds. An unresolvable uid
is refused; an unresolvable `char_id` is still skipped, because a stale id from
a browser is a UI bug the author cannot act on while a uid is a claim the
caller made.

Generation persists its expensive pure prefix — the two model calls — before
anything writes, so a retry of the same request replays it for free. A run
interrupted **after** it began planting rooms is refused rather than repeated,
because `_remap_generated_town` reads live state and replaying it would plant
the same town twice; `GET /charters/job` reports it and `DELETE` clears it.

The retired ladders were served to the UI as data (`offscreen_life_levels`,
`LIVING_WORLD_DESCRIPTIONS`), on the stated reasoning that a menu should render
the engine's own ladder rather than a copy that drifts. The reasoning stands
for whatever dial comes next.

---

## 6. Generating a lived location

`world/charter_runtime.generate_lived_location` is the one entry point. It
retrieves lore, proposes a plan, closes it deterministically, plants a
prose-free room graph, pre-names residents, simulates only the newly added
location, and writes a historian pass whose claims cite actual pre-simulation
events. Existing locations are preserved and collisions namespaced.

Limits, all real constants: `MAX_CATCHUP_HOURS = 720.0`,
`DEFAULT_PRESIM_TAIL_HOURS = 96.0`, `CAST_HISTORY_REQUEST_CAP = 16`.

Character history is **routed**, not universally simulated. Seven modes
(`story/history_routing.py`, `ROUTE_CHOICES`):

| Mode | Anchor / authority | What it generates |
|---|---|---|
| `auto` | inferred | travel language → `visitor`; residence + shared setting → `resident`/`moving_institution`; else `authored_only`. Competence or profession is never evidence of tenure. |
| `resident` | `fixed_place` / mixed | placed as a featured Charter body; 10–16 generated recent-life memories, a career summary, an overview |
| `moving_institution` | `bounded_moving_institution` / mixed | identical to `resident`, for a ship, caravan or unit that carries its own place |
| `visitor` | `itinerary` / authored | no Charter placement, no invented local career; a **cited** journey compiler over card and lore. Failure degrades to authored-card-only. |
| `generated_journey` | `itinerary` / generated | invents a travel history, minimum three usable events. Failure **re-raises**. |
| `authored_only` | — | preserves authored history, generates no past events |
| `none` | — | no history work |

Generation is **not** transactional and **not** resumable. It makes several
model calls and writes as it goes; a server restart mid-generation leaves the
work where it stopped. (`story/importers.py`'s `lore_gen_jobs` is the in-tree
pattern for making a multi-call generation resumable — per-unit persistence as
work lands, and a per-process owner token so a `running` row owned by a dead
process is detected exactly, with no staleness timeout to tune.)

---

## 7. Traps

Each of these is a place where the code does something other than what a
reasonable reading of a name, a default or a docstring predicts.

**No setting stops the world's own causes, and none ever did once they ran.**
Already-minted scheduled events fire whatever any dial says —
`commit_transit_sweep` and `mechanics_sweep` read no setting anywhere in the
path (`persist/commit_mechanics.py`'s `commit_transit_sweep` says so) — and
since 2026-11-01 there is no ladder left to set: arrivals, news, expiry and
consequences land on the clock in every story.

**Nothing gates any Charter path.** The catch-up tick was gated by the
`offscreen_life` ceiling until 2026-09-04, and that was the single most
misleading thing about the old ladder; a charter in the registry advances every
beat. Four other Charter paths never carried a gate at all:
`commit_charter_observations`, an ordinary commit domain writing bodies'
private claims from `director_resolve.public_evidence` every beat and letting
the bodies in a figure's room see the figure (`sight_figures_in_scene`)
(`persist/commit_background.py`, `commit_charter_observations`);
`apply_presence_conduct`, which mutates the registry from `background_react`
output (`world/charter_runtime.py`); the arrival-residue read; and the
planted-structure read. Charter *generation* is ungated too (`web/app.py`,
`charters_generate`).

**The carrier network is ungated in the same way, and it is large.**
`world/crowds.py`, `story/carriers.py` and `story/couriers.py` read no
setting. This is what approach C became when it left the ladder (before the
ladder itself went): rumour transport is core epistemic physics, on the stated
reasoning that a setting able to disable witnessing, speech or letters makes
the world incoherent. It is not configurable, and it does not stop.
`story/artifacts.py`'s wording mint, which read the old ceiling, is ungated
since 2026-09-20 and bounded by its own attempt cap.

**A consequence's truth and its surface are different things, and neither is
a setting.** A fired fuse's CONTENT reaches a reader in two places — the
walk-in notice (`world/mechanics.py`, `_fire_due_events`, only where the player
stands) and the re-entry residue read (`world/routines.py`, `residue_for`).
Beneath them is the truth spine and the physics on top of it: a fired row is
promoted to `world_events` like any other kind, so the gap skeleton can report
that something of kind `consequence` happened at a place during an absence
(the kind and the place, never the `what`), and the carrier rail may hand its
`witnessed` surface to a body physically standing there. `record_obligations`
accrues a place's history whether or not anybody ever arrives
(`world/living_world.py`). Until 2026-09-07 the mint itself was gated, which
threw away every fuse the prose author declared in the default chat; a fuse is
Director-adjudicated causality, so it is recorded whatever happens next
(review 2026-09-07, A82).

**`max_bubbles` refuses at the opening, never by pausing.** A character
refused a thread is exactly where every absent character stood before bubbles
existed — with the Charter still moving them if they are a townsperson — and
the refusal names the cap in a warning, so it cannot be read as the detector
failing (`world/spatial_frames.detect_and_reconcile`). Every open bubble runs
every beat; a cap on advancing would be a freeze wearing a number
(`agents/offscreen_beat.OFFSCREEN_BEATS_ARE_UNCAPPED`).

**`background_config` does not validate or clamp.** It merges the stored blob
over the defaults verbatim (`story/scene.py`, `background_config`). Every
ceiling lives elsewhere, so anything writing the config through `wset` directly — a test, a
demo seed, a tool — bypasses all of them except `max_reactors`'.

**A background presence is not scope-filtered by room.** There is no
room filter in the `pick_background_reactors` candidate loop; `here` is
computed but used only for two of the eight signals
(`persist/commit_background.py`, `pick_voice_demand`). A presence with dialogue
history in a room the player left ten turns ago still qualifies.
`managed_presences` **does** filter by ambient scope (`agents/background.py`),
so the two paths disagree about co-presence.

**The salience backstop is cheap; the scene manager is not.** These are two
paths through one step and their costs differ by an order of magnitude.
Measured 2026-08-24 over nine live chats, 816 `background_react` steps: the
backstop produced a reaction on 0–10% of beats (its docstring's "common case"
claim holds — `selected: []` on the rest), while chat 67, the one story running
`scene_life: full`, fired on **48 of 50 beats** and spent 51 model calls. That
is the setting working as designed — `full` means voice the populace every beat
— but it is a per-turn cost, and nothing in the config surface says so before
you turn it on.

Note when instrumenting this: the two paths record their spend in different
fields. The backstop writes `_engine_notes.llm_calls`; the manager writes
`agent_calls` and leaves `_engine_notes` null. Counting only the first
undercounts a `scene_life` story to zero.

**`ambient` refuses divergent perception, not directed lines.** Both
`story/scene.py`'s `background_config` docstring and `agents/background.py`'s
`_audience_map` docstring say a line "directed at one of them is withheld";
the actual test `_audience_map` applies is whether the audience map has more
than one distinct hear level. A line aimed at one presence but heard
identically by all IS admitted; a line aimed at nobody that
reaches two presences differently is NOT.

**`ambient`/`full` do not replace the backstop.** Both can run in one beat, and
`_merge_stage_results` then emits `mode: "scene_life:full+background_react"`. A
reader keying off `mode == "background_react"` misses those beats.

**Charter-linked presences are excluded from the scene manager** by design —
Charter history is private per body and a shared manager prompt is read by every
voice in it (`agents/background.py`, `managed_presences`). Enabling
`scene_life` does not batch an institution.

**Promotion is irreversible spend with an implicit model call.** Calling
`promote_background_character(cid, name)` with no `sheet` triggers
`draft_promoted_character` (`persist/commit_background.py`,
`promote_background_character`). Never call it inside the turn's write
transaction. And Charter promotion does not delete the
body — its key remains in `bodies` and can still appear on a watch bill; only
cognition and motion move out (`world/charter_run.py`'s `step`, the promotion
exclusion).

**A blank authored field reads as working.** A post with no `serves` is staffed
harmlessly rather than dropped; an upkeep missing from `priority` is appended
rather than dropped. Both are deliberate anti-silent-loss choices, and both
mean an incomplete sheet produces no complaint — the same failure mode
`CLAUDE.md` records for `psychology.drive`.

**`max_bubbles` is chat-global while the threads it caps are frame-scoped.**
Lowering it refuses the next opening in every era of the chat at once,
including ones the player is not standing in.
