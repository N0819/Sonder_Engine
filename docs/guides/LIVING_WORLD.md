# The Living World

What happens when nobody is looking, and every switch that decides how much of
it happens. Every claim here is against source — `world/living_world.py`,
`world/offscreen.py`, the twenty-nine `world/charter_*.py` modules,
`agents/background.py` with `persist/commit_background.py`, and
`story/scene.py`'s two ladders.

**Nothing here is one feature.** Four subsystems with overlapping names are
governed by six independent settings that must AGREE before anything happens,
and every one of them defaults to doing less than a reader expects. That
composition is what this guide exists to state; it cannot be derived from any
single module, and no error is raised when it is unsatisfied.

Related: [`design/DESIGN_LIVING_WORLD.md`](../design/DESIGN_LIVING_WORLD.md),
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
| **Charter** | The institution simulator: people, duties, upkeeps, beliefs, goods, reporting lines. Twenty-nine `world/charter_*.py` modules behind `world/charter.py`. A *thing that runs*. | Not a setting. Nothing named `charter` turns Charter on. |
| **Living World** | Four author-selectable **policies** deciding which world-generation machinery runs, each `off`/`floor`/`ceiling`. `world/living_world.py`. | Not a simulator. It is the switchboard, not the thing switched. |
| **off-screen life** | The chat-level **authority ceiling** over all of the above, five rungs. `story/scene.py:1866`. | Not an instruction that anything must happen — only a cap on what may. |
| **background life** | Voicing unregistered people who are **present in the room**, during the turn. `agents/background.py`. | Not off-screen anything. Its subjects are on screen. |

**The boundary sentence, if you remember one thing.** Background life voices
bodies that are PRESENT IN THE SCENE and UNREGISTERED (no `chat_chars` row,
tracked only in `background_presences`), during the turn, inside the
`background_react` step. Off-screen life advances bodies that are ABSENT FROM
THE SCENE and REGISTERED (`chat_chars.status='dormant'`, with sheets), between
turns, inside `world/offscreen.py`. (`persist/commit_background.py:1071`,
`world/offscreen.py:1260`.)

### Two things called "ceiling"

They are different, they interact, and confusing them is the most common way to
mis-configure a story.

- **A depth ceiling** is the top of one Living World approach's own ladder —
  the model-assisted tier of *the same mechanism* whose `floor` is
  deterministic. `world/living_world.py:69`.
- **The off-screen ceiling** is the chat's `offscreen_life` rung acting as an
  authority cap *over all four approaches at once*. It rides inside a
  living-world config dict under `OFFSCREEN_CEILING_KEY`, in memory only,
  between read and use. `world/living_world.py:183`.

Its one durable home is `dialogue_config["offscreen_life"]`.
`normalize_living_world` builds its output solely from
`LIVING_WORLD_APPROACHES`, so `offscreen_life` cannot acquire a second stored
spelling under the living-world key — it is dropped on every write
(`world/living_world.py:206`).

### Other collisions worth knowing before you grep

| Term | Here it means | Elsewhere it means |
|---|---|---|
| `place_obligations` | an **approach** key in the ladder | also the **world-KV key** of the obligation ledger (`OBLIGATION_KEY`, `world/living_world.py:476`) — same string, different namespace |
| `post` | a Charter duty slot | `scene.stations` is a body's within-room position; the model docstring names this the one naming trap (`world/charter_model.py:23`) |
| `registry` | the frame-scoped `charters` KV blob | `room_registry` is the cross-frame room-identity ledger |
| `character_agent` | top rung of the per-chat ladder | `schemas.BehaviorController` uses the identical five names **per character** (`story/scene.py:1792`) |
| `route` | a character-history topology decision (`story/history_routing.py`) | a spatial edge in `world/spatial.py` |
| `structure` | a planted, prose-free town skeleton in `world/structure.py`, composed into the live scene on demand | not a Charter primitive; it holds rooms, not people |
| `gap` | "what changed about subject X between turn N and now" (`world/gaps.py`), model-free | not an off-screen tick; it *reads* `offscreen_log`, it does not write it |

---

## 1. Every gate

Six axes. All of them must permit a behaviour before it occurs.

| Gate | Values | Default | Stored | Set by | Unknown value |
|---|---|---|---|---|---|
| `offscreen_life` | `inert`, `deterministic`, `reactive`, `stochastic`, `character_agent` | `stochastic` | `dialogue_config`, chat-global | Dialogue Config UI | falls to the **default**, not the floor (`story/scene.py:1892`) |
| `living_world.<approach>` | `off`, `floor`, `ceiling` × four approaches | `off` | world KV `living_world`, per chat | `PUT /api/chats/{id}/living_world` | unknown **depth** → default `off`; unknown **approach key** → silently dropped |
| `max_offscreen_actors` | `0`–`12` | `3` | `dialogue_config` | Dialogue Config UI | clamped (`story/scene.py:1992`) |
| `background_config.scene_life` | `off`, `ambient`, `full` | `off` | world KV `background_config` | `PUT .../background_config` | treated as `off`, silently — there is no `normalize_scene_life` |
| `background_config.max_reactors` | `1`–`3` | `1` | as above | as above | clamped in the stage, not in the config reader |
| `simulation.offscreen_agent` | bool | `false` | the character card | card editor | see the trap in §7 |

Two of these have a second, quieter axis beside them:
`background_config.max_managed` (1–8, clamped only on the HTTP route,
`web/app.py:4676`), and `simulation.offscreen_importance`, the manual
importance override — which ranks the **free** profile rung and can never opt
anything in (`world/offscreen.py:157`).

### The two ladders, side by side

`offscreen_life` rungs are **cumulative** — at `character_agent` a single epoch
runs the free seeded draw *and* schedules profile ticks *and* schedules agent
ticks, three producers over the same dormant cast, each capped independently by
the same `max_offscreen_actors` number (`world/offscreen.py:1057`, `:1432`,
`:2138`).

| Approach | What its floor does | Ceiling built? | Floor needs | Ceiling needs |
|---|---|---|---|---|
| `routine_residue` | the world's default motion; payload-side only, persists nothing | no | `deterministic` | `stochastic` |
| `scheduled_consequence` | mints consequence fuses onto the clock | no | `deterministic` | `stochastic` |
| `place_obligations` | surfaces a place's accrued owed history | no | `deterministic` | `stochastic` |
| `antagonist_ladder` | fires authored plan stages on typed triggers | **yes** | `reactive` | `character_agent` |

Three of the four have no built ceiling: setting them to `ceiling` marks intent
and runs the floor (`LIVING_WORLD_BUILT`, `world/living_world.py:92`). Only
`antagonist_ladder` has one.

**`effective_depth` never errors.** It lowers a requested depth to the highest
depth at or below it that is both BUILT and within the off-screen ceiling
(`world/living_world.py:232`). Ask for something unavailable and you get
something quieter, silently. Read `effective`, never `value`, when you want to
know what will run — the API returns both for exactly this reason
(`world/living_world.py:294`).

---

## 2. "I want X to happen"

The payload. Each row is a conjunction: **every** requirement must hold.

| Goal | Requirements |
|---|---|
| Nothing at all off screen | `offscreen_life = inert` **and** all four approaches `off`. Note `inert` alone is not enough — see §7. |
| Scheduled effects only (arrivals, expiry, news latency) | `offscreen_life = deterministic` |
| A consequence fired later from an adjudicated declaration | `offscreen_life ≥ deterministic` **and** `scheduled_consequence = floor` |
| A place carrying its owed history into a scene | `offscreen_life ≥ deterministic` **and** `place_obligations = floor` |
| An authored antagonist advancing a plan unwatched | `offscreen_life ≥ reactive` **and** `antagonist_ladder ≥ floor` |
| A named absent character advancing their **own** plans | `offscreen_life = character_agent` **and** `antagonist_ladder = ceiling` **and** the card's `simulation.offscreen_agent = true` **and** `max_offscreen_actors > 0` **and** that character's `chat_chars` status is `dormant` **and** the beat minted an epoch **and** that mind has a *private reason* |
| An institution **catching up** — its people, duties, markets and gossip advancing over elapsed time | `offscreen_life ≥ deterministic` (`world/charter_runtime.py:1071`) plus a charter in the registry. This gate covers the catch-up tick **only** — see §7. |
| A room showing what changed while it was unwatched | `routine_residue ≥ floor` **and** `offscreen_life ≥ deterministic` **and** a declared movement — but Charter incidents reach the same payload slot ungated, and are prepended ahead of routine texture (`agents/director.py:2594`) |
| An unregistered presence speaking in the room | none of the above — this is `background_react`, gated only by `pick_background_reactors` and `max_reactors` |
| A whole location's populace voiced in one call | `background_config.scene_life = ambient` or `full` |

**The paid-tick row is the one people get wrong**, and `AGENTS.md:97`'s
"three gates compose" is correct as a conjunction but incomplete as a
checklist. The code adds an epoch-opportunity gate, a non-empty-epoch-id gate,
the actor cap and a dormant-status gate (`world/offscreen.py:2132`, `:2135`,
`:2143`, `:1266`). Satisfy only the three named gates and you still get nothing
on most beats — correctly.

A **private reason** is the firewall-safe justification a paid tick requires:
an owned plan with status `active`, or a carried report acquired later than
that subject's own last paid tick (`world/offscreen.py:1327`). Importance
ranks nothing here; truncation is by `chat_chars.char_id` ascending
(`world/offscreen.py:1340`).

An **epoch** is one frame-scoped off-screen opportunity, minted at most once
per beat when `epoch_reasons()` is non-empty, carrying one `epoch_id` that
seeds and idempotence-stamps every tick derived from it
(`world/offscreen.py:496`). It is not a turn — many turns of conversation can
pass inside one epoch, which is the point.

---

## 3. Charter, in five nouns

Enough vocabulary to read any `charter_*` module. All in
`world/charter_model.py` unless noted.

| Noun | What it is |
|---|---|
| **upkeep** | A condition the institution owes, held at or above a `floor`, drifting down at `drift_per_hour` unattended and back up at `service_per_hour` when a competent body tends it. `:108` |
| **post** | A duty slot: a place, a competence requirement, the upkeeps it `serves`, an optional `reports_to` line, a closed `authority` list. `:141` |
| **competence** | `{tag: level}` on a body, author-owned tags. `meets()` is satisfied only when every requested tag is present at or above its level. `:88` |
| **watch** | `{post_key: body_key}` for one planning window — who the institution *tried* to put where. Produced by `plan_watch`, carried on the charter so role continuity survives persistence. `world/charter_plan.py:87`, stored `:286` |
| **charter** | One institution: upkeeps, posts, bodies, the roster it believes it has, its `priority` ordering of what it abandons last, plus every layered store. `:238` |

Three more you cannot proceed without:

- **body** — a person the charter may assign. `key` (durable institutional id)
  is separate from `name` (scene-facing identity). `available` is **ground
  truth**. `:168`
- **roster** — what the charter *believes* about its people, with its own
  competence and availability claims, improving on observation and decaying
  otherwise (`world/charter_roster.py`). The planner never reads `bodies`; it
  reads the roster. That gap is deliberate and is where institutional error
  comes from.
- **figure** — a person the institution can know without owning: the player, a
  major character. Never rostered, never planned, never blamed, holds no mind
  inside the charter (`world/charter_figure.py:34`).

### The module map

Twenty-nine files, six themes.

| Theme | Modules |
|---|---|
| **Shape** | `charter_model` (the primitives), `charter_identity`, `charter_space` |
| **People** | `charter_needs`, `charter_temper`, `charter_feel`, `charter_move`, `charter_figure`, `charter_promote` |
| **Belief** | `charter_mind`, `charter_roster`, `charter_talk` (gossip), `charter_news`, `charter_social`, `charter_politics`, `charter_observe` |
| **Doing** | `charter_plan` (staffing), `charter_practice` (situations and affordances), `charter_decide` (agendas and orders), `charter_commitment`, `charter_author`, `charter_intervene` |
| **Material** | `charter_economy`, `charter_drift` |
| **Time and I/O** | `charter_run` (advance a window), `charter_runtime` (the production seam), `charter_generate`, `charter_history`, `charter_log` |

**`world/charter.py` is an internal facade, not the public API.** Four siblings
are structurally outside it and must be imported directly by engine code —
`charter_generate`, `charter_history`, `charter_observe`, `charter_runtime`.
Its docstring enumerates the seam for only ten of the twenty-nine; treat that
as historical framing, not coverage. And unlike `world.spatial`,
`agents.director`, `persist.commit` and `mind.memory`, this facade is **not**
machine-enforced — `tools/project_check.py`'s `FACADE_FAMILIES` does not list
it. Direct sibling imports work. That is not permission.

---

## 4. Storage

| What | Where | Frame-scoped |
|---|---|---|
| Living World config | world KV `living_world` | no |
| off-screen ceiling | `dialogue_config.offscreen_life` | no (chat-global) |
| Charter registry | world KV `charters` | **yes** |
| obligation ledger | world KV `place_obligations` | **no** — chat-global across every era |
| planted town skeletons | world KV `structures` (`world/structure.py`) | **no** — chat-global |
| off-screen epoch / plans | world KV, per frame | **yes** |
| `offscreen_log` — the append-only tick ledger | world KV, per frame | **yes** |
| background presences | world KV `background_presences` | **yes** |
| fired consequences, Charter incidents | `scheduled_events` → `world_events` | rows carry `frame_id` |

`charters` being frame-scoped has a sharp edge: a bare `wget(cid, "charters")`
reads a *different row* than `registry_for(cid, frame_id)` whenever a frame is
active — the key on disk becomes `charters\x1efr<frame_id>`
(`core/db.py:82`). Always go through `registry_for` / `save_registry`.

`registry_for` also normalizes on read, so a round trip is **lossy** for any
field `normalize_charter` / `normalize_registry` does not enumerate. Adding a
persistent charter field means adding it to `normalize_charter`, or it will not
survive one read. `normalize_registry` silently discards any `recent_events`
key it finds (`world/charter_runtime.py:73`); incidents belong on
`scheduled_events`.

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

- A frame **split** seeds the away frame from exactly seven parent keys —
  `known`, `simulation_clock`, `standing_intentions`, `pending_obligations`,
  `shadow_profile`, `background_presences`, `offscreen_log`
  (`world/spatial_frames.py:844`). `charters`, `offscreen_epoch` and
  `offscreen_plans` are **not** among them.
- A frame **merge** reconciles only `simulation_clock`, `known`,
  `relationships:<id>` and `scene` (`world/spatial_frames.py:998`). Nothing a
  Charter, a plan or a standing intention did in the away frame comes back;
  those rows are orphaned.
- `create_frame` writes no world rows at all (`core/frames.py:98`), so a newly
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
| `GET/PUT /api/chats/{id}/living_world` | read/write the four-approach config; the PUT returns the normalized result so a dropped key is visible immediately |
| `GET/PUT /api/chats/{id}/charters` | read/write the frame-scoped registry |
| `GET /api/chats/{id}/charters/diagnostics` | inspect belief, judgment and planning state; `?body=` selects one body |
| `POST /api/chats/{id}/charters/generate` | generate one lore-grounded lived location; the body's `population` (an integer) is a closure input the closer lands within `POPULATION_TOLERANCE`, and the result's `closure` record says what was asked, planned and closed, which head posts were held to one holder, and which berths were split |

The three `charters` routes take a `frame_id` query parameter, and the
mutating ones call `_require_frame_idle` first — a turn in flight refuses a
Charter write with a 409. **`PUT /living_world` does neither**: it takes no
frame and holds no guard, which is coherent (the ladder is chat-global) and
worth knowing before you assume the four behave alike. `GET /charters` returns the registry plus `character_history_routes`,
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

Four hooks, behind two capability names. Importing `world.charter_runtime`
directly is still outside the boundary; these are the supported path.

| Surface | Capability | Does |
|---|---|---|
| `story_view(...)["living_world"]` | none — the key is always present | the ladder as stored **and as it will actually run**, the off-screen ceiling and actor cap, the background config, a row per institution, and `registry_warnings` |
| `story_view(..., charters="full")` | as above | the complete registry — the same bytes `GET /charters` serves |
| `provision_story(..., offscreen_life=, living_world=)` | `living_world_provisioning` | set the ladder inside the same transaction that creates the story; the result carries the effective ladder back |
| `api.generate_lived_location(...)` / `api.living_world_job(...)` | `living_world_generation` | add an inhabited place, and see whether a previous attempt was interrupted |

Two things about that table are load-bearing.

**Read `effective`, never `value`.** The provisioning result and the slice both
carry `approaches`, which is `living_world_levels`' own output — so `value`
(what was asked for) and `effective` (what will run) come from the same
`effective_depth` the gates use and cannot drift. A caller that reads back only
its own request learns nothing, because the clamp is silent.

**The arguments are refused, not normalized** — the opposite of the HTTP
routes, and deliberate. A host typing into a panel sees the normalized answer
come straight back and can correct it. A campaign sees nothing, and
`normalize_offscreen_life` falls to the DEFAULT rather than the floor, so a
typo would buy *more* off-screen life than was asked for.

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

The ladders **are** served to the UI as data — `offscreen_life_levels`
(`web/app.py:4454`) and `LIVING_WORLD_DESCRIPTIONS` ride with the config, on the
stated reasoning that a menu should render the engine's own ladder rather than
a copy that drifts. Any future developer-facing surface should extend that
rather than restate these tables.

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
(`story/history_routing.py:18`):

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

**`inert` does not mean nothing happens.** It stops new minting. Already-minted
scheduled events keep firing — `commit_transit_sweep` and `mechanics_sweep`
have no `offscreen_life` gate anywhere in the path
(`persist/commit_mechanics.py:132` says so explicitly). A story set to `inert`
keeps delivering the arrivals, news and consequences it already scheduled.

**`offscreen_life` gates the Charter CATCH-UP TICK only.** This is the single
most misleading thing about the ladder. Four other Charter paths carry no
ladder gate at all and run at every rung including `inert`:
`commit_charter_observations`, an ordinary commit domain writing bodies'
private claims from `director_resolve.public_evidence` every beat and letting
the bodies in a figure's room see the figure (`sight_figures_in_scene`)
(`persist/commit.py:453`); `apply_presence_conduct`, which mutates the registry
from `background_react` output (`persist/commit_background.py:1110`); the
arrival-residue read; and the planted-structure read. Charter *generation* is
ungated too (`web/app.py:4633`). A story set to `inert` still accrues Charter
evidence, still forms beliefs, and can still have a whole town generated into
it.

**The carrier network is ungated in the same way, and it is large.**
`world/crowds.py`, `story/carriers.py` and `story/couriers.py` contain zero
`offscreen_life` and zero `living_world` references. This is what approach C
became when it left the ladder: rumour transport is core epistemic physics, on
the stated reasoning that a setting able to disable witnessing, speech or
letters makes the world incoherent (`world/living_world.py:71`). It is not
configurable, and it does not stop.

(A fifth consumer of the ladder sits outside both `world/offscreen.py` and
`world/charter_runtime.py`: `story/artifacts.py:411` gates artifact wording on
`offscreen_life ≥ stochastic`.)

**Turning an approach off is equally asymmetric.** Setting
`scheduled_consequence = off` stops new fuses being minted; it does not stop
minted fuses firing, and it does not stop `record_obligations` accruing
history — that function is ungated by the `place_obligations` setting entirely
(`world/living_world.py:492`). The principle is *settings gate surfaces, never
truth*; grep for a setting to find where a ledger is controlled and you will
find the surface, not the accrual.

**`offscreen_life = character_agent` alone fires nothing.** Both the `reactive`
and `character_agent` rungs are additionally gated through
`living_world_allows('antagonist_ladder', ...)` (`world/offscreen.py:898`,
`:2138`), whose default is `off`. A chat raised to `character_agent` and
nothing else runs zero reactive stages and zero agent ticks, silently.

**And the converse.** `antagonist_ladder = ceiling` without raising
`offscreen_life` does not turn the mechanism off — `effective_depth` clamps to
`floor`, which still fires authored plan stages. The only fully-off states are
`antagonist_ladder = off` or `offscreen_life = inert`.

**The string `"false"` in a card opts the character IN.**
`character_offscreen_agent` applies `bool()`, and `bool("false")` is `True`.
The legacy branch is no safer — it applies the same `bool()`
(`story/character_schema.py:1166`). Only a real JSON boolean means what it
says, so an imported or hand-edited sheet carrying `"offscreen_agent": "false"`
buys paid model calls for that character.

**`max_offscreen_actors` is one number serving three caps** — the free seeded
draw, the profile candidates and the paid agent candidates
(`world/offscreen.py:1055`, `:1454`, `:2147`). Raising it at `character_agent`
multiplies paid spend in a way the name does not suggest.

**The paid rung disappears when the player's room cannot be resolved.**
`schedule_profile_ticks` returns `None` with skip reason `no_player_room`
(`world/offscreen.py:1445`). This reads as the feature being off rather than as
a missing anchor.

**`background_config` does not validate or clamp.** It merges the stored blob
over the defaults verbatim (`story/scene.py:2099`). Every ceiling lives
elsewhere, so anything writing the config through `wset` directly — a test, a
demo seed, a tool — bypasses all of them except `max_reactors`'.

**A background presence is not scope-filtered by room.** There is no
room filter in the `pick_background_reactors` candidate loop; `here` is
computed but used only for two of the eight signals
(`persist/commit_background.py:1541`). A presence with dialogue history in a
room the player left ten turns ago still qualifies. `managed_presences` **does**
filter by ambient scope (`agents/background.py:546`), so the two paths
disagree about co-presence.

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
`story/scene.py:2087` and `agents/background.py:559` say a line "directed at
one of them is withheld"; the actual test is whether the audience map has more
than one distinct hear level (`agents/background.py:594`). A line aimed at one
presence but heard identically by all IS admitted; a line aimed at nobody that
reaches two presences differently is NOT.

**`ambient`/`full` do not replace the backstop.** Both can run in one beat, and
`_merge_stage_results` then emits `mode: "scene_life:full+background_react"`. A
reader keying off `mode == "background_react"` misses those beats.

**Charter-linked presences are excluded from the scene manager** by design —
Charter history is private per body and a shared manager prompt is read by every
voice in it (`agents/background.py:527`). Enabling `scene_life` does not batch
an institution.

**Promotion is irreversible spend with an implicit model call.** Calling
`promote_background_character(cid, name)` with no `sheet` triggers
`draft_promoted_character` (`persist/commit_background.py:1683`). Never call it
inside the turn's write transaction. And Charter promotion does not delete the
body — its key remains in `bodies` and can still appear on a watch bill; only
cognition and motion move out (`world/charter_run.py:149`).

**A blank authored field reads as working.** A post with no `serves` is staffed
harmlessly rather than dropped; an upkeep missing from `priority` is appended
rather than dropped. Both are deliberate anti-silent-loss choices, and both
mean an incomplete sheet produces no complaint — the same failure mode
`CLAUDE.md` records for `psychology.drive`.

**`offscreen_life` is chat-global while everything it governs is
frame-scoped.** Changing the rung changes behaviour in every era of the chat at
once, including ones the player is not standing in.
