# Audit — Writers' Room tooling and the information carriers (2026-11-01)

Auditor scope: `story/room_sketch.py`, `story/room_proposals.py`, `story/room_frontier.py`,
`story/room_conversation.py`, `story/location_design.py`, `story/room_slice.py`,
`story/room_research.py`, `story/room_calls.py`, `story/mandates.py`, `story/carriers.py`,
`story/couriers.py`, `story/artifacts.py`, `story/journey_history.py`. Working tree at 84f3de23
(clean). Reproductions ran only against stubs or scratch databases under
`S/story_room_audit/` (never a repo `*.db`). One focused test file was run
(`tests/test_artifacts.py`: 11 passed).

## Scope read

Read IN FULL (every line):

- `story/carriers.py` 1-1369
- `story/couriers.py` 1-1170
- `story/artifacts.py` 1-653
- `story/journey_history.py` 1-487
- `story/mandates.py` 1-809
- `story/room_frontier.py` 1-726
- `story/room_slice.py` 1-561
- `story/room_sketch.py` 1-1227
- `story/room_proposals.py` 1-906
- `story/room_conversation.py` 1-582
- `story/location_design.py` 1-577
- `story/room_research.py` 1-376
- `story/room_calls.py` 1-249

Read in part, to trace callers/readers (not audited as a whole):
`agents/character.py` 3440-3500 (`tellers_as_known`), 4615-4660 (the carried-report payload);
`persist/commit_mechanics.py` 300-470 (`commit_world_event_spine`, `commit_information_carriers`);
`persist/commit.py` 482-490, 552-681, 880-905; `world/charter_runtime.py` 794-830, 964-1000,
2560-2600, 2830-2960 (`_event_surface`, `_scheduled_row`), 3670-3700 (`post_spoor` caller),
4040-4240 (`carrier_entries`, `save_carrier_state`, `clock_anchor`); `world/charter_news.py` 40-80
(`WITNESSABLE`), 187-300, 535-560; `world/charter_log.py` 335-360; `world/crowds.py` 700-790;
`agents/common_rooms.py` 79-190, 660-690; `agents/director_views.py` 660-720;
`agents/common_identity.py` 34-60, 117-215; `agents/common_names.py` 190-220; `story/scene.py` 1313,
1483-1520, 1828-1836; `core/db.py` 33-200, 224-255, 2349-2440, 2993-3150; `core/jobs.py` 91-180;
`world/spatial_barriers.py` 331-400; `world/spatial_routing.py` 1184-1225;
`world/spatial_identity.py` 343-380; `world/structure.py` 2450-2472; `world/spatial_frames.py`
1695-1715; `story/plot_packages.py` 353-387 and `publish_package`; `story/opening_plan.py` 40-75;
`agents/story_planner.py` 835-880, 2141-2150, 2375-2420; `agents/dramaturge.py` 235-262;
`llm/schemas.py` 2624-2664; `agents/director_evidence.py` 470-500; `agents/director_prose.py`
840-870; `language_packs/{en,ja}/cards/system_prompts/prompts/{room_sketch,artifact_wording}.txt`.

Skimmed only (other auditors own them): `story/room_tools.py`, `story/plot_packages.py`.

## Findings

Severity counts (34 findings): LEAK 3, CORRUPTION 6, CRASH 1, WRONG-SCENE 9, SILENT-NOOP 8, DEAD 2, STALE-DOC 5.
(F1 overlaps `audits/world_charter_core.md` F2; this report adds the reader side, the crowd path,
the degradation artefact and the fix site, as asked.)

### F1 — A charter event's engine body keys reach minds word for word as a firsthand claim (reader side confirmed; fix site)
- Severity: **LEAK** where a body key is a name (authored registries; the repo's own fixtures key
  bodies `ilse`, `raul`), **WRONG-SCENE** otherwise (generated keys `{post}:{NNNN}`). Also a
  **language-pack hazard**: the surface is an English template. Confidence: **CONFIRMED** (traced
  end to end; degradation snippet below).
- Producer: `world/charter_runtime.py:2846-2896` (`_event_surface`: `f"{subject} caused harm to {toward}"`,
  `subject`/`toward` are raw `body`/`post`/`subject` keys) and `:2939-2945`
  (`public = _event_surface(event) if kind in WITNESSABLE`; `"witnessed": public`).
- Carrier side: `story/carriers.py:229` (`witnessed = " ".join(str((payload or {}).get("witnessed") ...`),
  `:194-198` (the standing-surface reader, same text), stored as `"claim": witnessed` at `:287`;
  crowds `:374`; caravan cargo `story/couriers.py:706`.
- Reader side (confirmed):
  - `agents/character.py:4635-4643`: `payload["carried_reports"] = tellers_as_known(chat, ..., reports_for_state(stored_state))`;
    `tellers_as_known` (`:3456-3480`) rewrites only `told_by`; `claim` passes verbatim.
  - Perception: `world/crowds.py:760-768` (`talk_view`: `"gist": claim`) -> `agents/common_rooms.py:156`
    (`"talk": crowds_model.talk_view(crowd)`), so a crowd that witnessed the event repeats the key
    sentence to every observer in its room.
  - Retellings never remove the key: `persist/commit_mechanics.py:425-436` hands `degradation` the
    registered display names and charter display names, never body keys. Snippet:
    ```
    degrade('warden:0001 caused harm to cook:0003', 1, names=['Ilse Brandt','Raul Ostrander'], places=['chapel'])
      -> 'warden:several caused harm to cook:several'      # the NNNN read as a count
    degrade('ilse caused harm to raul', 3, names=[...])     -> 'ilse caused harm to raul'
    ```
- Scenario: a charter `harm_done` (`body: warden:0001`, `subject: cook:0003`) fires in the chapel;
  a cast member standing there (or walking in later, F3) holds "warden:0001 caused harm to
  cook:0003" as `witnessed_surface`; told on, the listener hears "warden:several caused harm to
  cook:several". With an authored registry, the bystander learns the names `ilse`/`raul` through no
  channel. In a Japanese story every one of these is English.
- Fix (producer, the class): build `witnessed` from what a bystander perceives — the post/role nouns
  `carrier_entries` already uses for charter-held news (`_post_words`/`_member_namer`,
  `charter_runtime.py:4119-4134`, "never by key") — rendered through the language pack; keep the parties
  structurally on the payload (`payload["charter_event"]` already carries the keys) so
  `advance_carriers` can render per observer at acquisition (known name via the `known` ledger, else the
  stranger label), as `tellers_as_known` does for tellers.
- Test: a charter `aid_given` world event between two unmet bodies lands in a room with a registered
  character; after `advance_carriers` the stored claim contains no `:NNNN` key and no display name the
  character does not know; a `ja` story's claim contains no ASCII template words.

### F2 — No consciousness gate anywhere in the carrier network: a sleeping or unconscious body acquires, is told, is delivered to, and reads
- Severity: **LEAK**. Confidence: **CONFIRMED** for the absence (grep: no `awake|asleep|unconscious|awareness`
  in `story/carriers.py`, `story/couriers.py`, `story/artifacts.py`, `world/crowds.py`); the audibility half
  is **PLAUSIBLE**.
- Where: `story/carriers.py:252-317` (acquisition tests `str(row["location_id"]) != current_room` only);
  `:1259-1262` (`if not speaker["room"] or speaker["room"] != listener["room"]` — the only listener test in
  `apply_tellings`); `story/couriers.py:544-583` (`_deliver`: addressee or up to 3 bodies by room);
  `story/couriers.py:1044-1083` (question); `story/artifacts.py:321-351` (read: `reader_room != artifact.room`).
- The engine already has the rule: `story/scene.py:1313` `NON_AWAKE_GATED = {"asleep","sedated","unconscious"}`,
  `awareness_map` (:1483), `apply_awareness_diff` (:1517), `awareness_of` (:1828); perception excludes a
  non-awake mind from its call (`agents/perception.py:4414-4421`).
- Scenario: Mora is knocked out in the square (awareness `unconscious`); a charter `accusation` fires there;
  `advance_carriers` files it on Mora as `witnessed_surface, retellings 0`; she wakes holding an
  eyewitness account of words spoken while she was out. Likewise an encoder `telling_ops` row naming an
  asleep listener is applied (speaker spoke + same room is the whole floor), and a courier to a place hands
  its message to a sleeper. Audibility: a whisper to one person, or a line across a vast hall, still copies the
  report to any named listener in the "room" — the floor relies on the encoder naming only hearers.
- Fix: build `amap = apply_awareness_diff(awareness_map(cid), resolved_state_diff)` once in
  `commit_information_carriers` and pass it in; skip acquisition and delivery for a body whose level is in
  `NON_AWAKE_GATED`, refuse a telling/question/read naming one (with a reason). Optionally, for a registered
  listener, require a line by the speaker among the listener's own `perception_outcome` observations. This
  subtracts only a channel that was closed — the rule perception already applies.
- Test: an unconscious registered body and an awake one in the room where a public surface lands — only the
  awake one acquires; a telling to an asleep listener is refused with "asleep".

### F3 — A newcomer acquires a PASSING ACT as an eyewitness: the standing-surface window does not tell a state from an act
- Severity: **LEAK** (an unseen act becomes firsthand knowledge). Confidence: **CONFIRMED** (traced; the
  existing test pins any-age surfaces as standing).
- Where: `story/carriers.py:154-204` (`standing_surfaces_reader`: `SELECT * FROM world_events WHERE ... AND
  location_id=? ORDER BY occurred_at DESC LIMIT ?`, keeps every row whose payload has `witnessed`, no age or
  kind test) and `:277-301` (stored with `"provenance": "witnessed_surface"`, `"retellings": 0`,
  `"told_by": ""`). Producers of passing acts: `world/charter_news.py:40-80` `WITNESSABLE` includes
  `accusation` ("an accusation made aloud"), `apology`, `aid_given`, `harm_done`, `goods_exchanged`,
  `report_confirmed/refuted`, `commitment_*` — all written to the rail by `_scheduled_row`.
- Scenario: at 14:00 the reeve accuses the miller in the chapel (charter `accusation`, witnessed by those
  present). At 20:00 Hal walks into the empty chapel; `advance_carriers` reads the chapel's newest three
  surfaces and files "X accused Y" on Hal as `witnessed_surface` — his payload now holds an eyewitness account
  of words spoken six hours before he arrived. The module's own intent (`:233-242`, "consequences are met as
  state when someone next stands where they landed" — the barred gate) covers states, not acts;
  `tests/test_standing_surfaces_are_per_room.py::test_a_quiet_rooms_surface_survives_a_busy_story` shows a
  surface of any age is returned.
- Fix: carry, at the producer, whether a surface STANDS (a state change: upkeep, stock, a barred gate) or
  PASSES (an act); `world_events.duration_seconds` is written as `0.0` for every row
  (`persist/commit_mechanics.py:375-383`) and could carry it. Offer only standing surfaces to newcomers (the
  arrival window); passing acts are acquired only by bodies present on the beat they fired (`event_rows`).
- Test: an `accusation` surface three story hours old in a room — a body walking in acquires nothing; an
  `upkeep_out_of_band` surface — acquired.

### F4 — A wording job landing during a turn commit erases that turn's notices (lost update)
- Severity: **CORRUPTION**. Confidence: **CONFIRMED** (reproduced on a scratch DB).
- Where: `story/artifacts.py:604-653` (`land_artifact_wording`): `artifacts = [... wget(cid, ARTIFACTS_WORLD_KEY, [])]`
  (:620) ... `wset(cid, ARTIFACTS_WORLD_KEY, artifacts)` (:650) — read-modify-write in a job thread with no
  `transaction()`. The turn's `run_artifacts` writes the same row inside the commit's outer transaction
  (`persist/commit.py:556`). The job's read sees the pre-commit row (WAL), its `wset` blocks on
  `_write_lock` until the commit ends, then overwrites it with the stale list.
- Reproduction (`S/story_room_audit/race_artifacts.py`): the "turn" thread, inside `transaction()`, appends
  bill `c1` and sleeps; the main thread calls `land_artifact_wording(cid, "artifact:a1", "HEAR YE", "", base_turn=5)`;
  output `after both: [('artifact:a1', 'posted', 'HEAR YE')]` — `c1` is gone. A bill torn down in that commit
  stands again by the same path.
- Fix: wrap the read-modify-write in `transaction()` (BEGIN IMMEDIATE takes the write lock before the read),
  as the charter landings do.
- Test: the reproduction shape — a held transaction posting a bill while a wording lands; both survive.

### F5 — `room_mandates` is read-modify-written without a transaction by four threads: grants and revocations are lost
- Severity: **CORRUPTION** (a revoked licence can come back; a granted one can vanish). Confidence:
  **CONFIRMED** (reproduced on a scratch DB).
- Where: `story/mandates.py:375-388` (`_load` / `_save` -> `wset_for_frame`), used by `grant_mandate`
  (:451-478), `expire_mandates` (:492-508, which writes on every read of the standing grants that finds a lapse),
  `close_request` (:523-536); `story/room_conversation.py:280-296` (`revoke_mandate`, the panel route). Writers
  run on the Planner's daemon thread (`converse_stream`), the fill/Dramaturge job threads, the commit tail and
  the HTTP route. `story/room_frontier.py:154-173` documents and fixes exactly this class for its own row
  ("a write that landed between another writer's read and its save was erased by construction").
- Reproduction (`S/story_room_audit/race_mandates.py`): a grant written inside a held transaction while the
  panel revokes another grant -> `[('You may plan rooms', 'revoked')]`: the second grant is gone. The reverse
  interleaving (a stale `grant_mandate`/`expire_mandates` save after the revoke) restores the revoked row as
  `active`. Any open turn transaction (seconds) widens the window, because both writers block on the lock
  holding pre-commit reads.
- Fix: one `_update(cid, frame_id, change)` under `transaction()` (the `room_frontier._update` shape) for every
  mandate writer, `revoke_mandate` included.
- Test: the reproduction shape, both directions.

### F6 — A proposal re-filed after a refusal gets the refused proposal's uid; judging it flips the old row and the new one is pending forever
- Severity: **CORRUPTION** (author ledger). Confidence: **CONFIRMED** (reproduced with stubbed storage).
- Where: `story/room_proposals.py:108-114` (`_uid(identity, frame_id)`, identity = kind + title),
  `:128` (uid minted from identity when absent), `:309-316` (dedupe only against `open|revised|accepted`),
  `:339-358` (`judge_proposal` acts on the FIRST row with the uid).
- Reproduction: file "The tide comes early", refuse it, file it again ->
  `rows: [('prop_3ff9d27782','refused'), ('prop_3ff9d27782','open')]`; judge the new one `accept` ->
  `[('prop_3ff9d27782','accepted', 2), ('prop_3ff9d27782','open', 0)]`, `pending: ['open']`.
  The refused proposal now reads accepted (with a package uid when one is passed); the new one is re-offered to
  every deliberation and, as "awaiting the Planner", is never dropped by `PROPOSALS_CAP`. The Dramaturge is
  shown only the last 12 standing proposals (`agents/dramaturge.py:240-247`), so a re-proposal of an old
  refused title is ordinary.
- Fix: refuse a re-file whose identity matches a settled row ("already refused: <reason>"), or mint the uid
  from identity + `filed_turn`/sequence so ids never repeat.
- Test: file, refuse, re-file, judge the second — the first stays `refused`, the second settles.

### F7 — A torn-down spoor comes back at the next charter landing (two representations of one carcass)
- Severity: **CORRUPTION**. Confidence: **CONFIRMED** (reproduced with stubbed storage).
- Where: `story/artifacts.py:440-449` (`post_spoor`: a spoor artifact whose `status != POSTED` is kept but its
  uid is NOT popped from `wanted`, so `fresh` re-creates it); caller `world/charter_runtime.py:3687-3690`.
- Reproduction: post one spoor; mark it `removed` (what `run_artifacts` OP_REMOVE writes); land again ->
  `artifact:spoor:94b97b... removed` AND `artifact:spoor:94b97b... posted` — the carcass is back, under a
  duplicated uid. The registry's spoor list and the artifact status are two stores of one fact; removal
  writes only one. `docs/UNBUILT_LIVING_WORLD.md:3033` ("Spoor stands in play until the Director removes it")
  assumes removal works.
- Fix: pop the uid from `wanted` for a removed spoor (a removed carcass stays removed until the registry
  forgets it), or route OP_REMOVE of a spoor to the registry record.
- Test: post spoor, remove it via `run_artifacts`, land the same registry — one row, `removed`.

### F8 — A courier dispatch or a posted bill puts a lie in a mind's own ledger with nothing the mind did behind it — and leaves it there when the op is refused
- Severity: **CORRUPTION** (a mind's private state). Confidence: **CONFIRMED** (order read; grounding absent).
- Where: `story/couriers.py:953-972` (`_invented_claim(...)`; `save_state(cid, sender, state, ...)` at :965)
  runs BEFORE the exhaustion check (:975-980), the route (:981-997, `continue` on "no passable route") and the
  duplicate check (:1017-1019); `story/artifacts.py:266-277` saves the invented claim before
  `"that notice is already on the wall"` (:300-302). Neither path asks whether the sender/poster did anything
  this beat; `apply_tellings` refuses a speaker who "said nothing this beat" (`story/carriers.py:1247-1251`)
  for exactly this reason ("the same grounding rule that stops the Director inventing an absent character's
  plan"). `reports_for_state` hands the invented row to the mind (`provenance: invented`).
- Scenario: the encoder writes `courier_ops: send` from a dormant cast member (any extant body is in
  `_cast_index`, charter bodies too) with a `claim`, to a room no passable path reaches. The op is refused
  ("no passable route"), but the sender now carries a row saying they invented that claim; next time they
  act, their payload tells them they made it up. With a route, the dispatch itself is a decision the mind
  never declared (owner ruling 2026-10-20: the Director writes undergoing, never deciding).
- Fix: validate the whole op first and file the invented row only on success; ground a send/post the way a
  telling is grounded (the sender's own declaration or line this beat), refusing otherwise.
- Test: a send with a claim and no route — refused, sender's ledger unchanged; a send from a sender with no
  declaration/line this beat — refused.

### F9 — Every generated journey in a Japanese story is refused as "thin", and the launch raises
- Severity: **CRASH**. Confidence: **CONFIRMED** (grounding reproduced; the model writing Japanese under the
  story's prompt policy is the other audit's trace).
- Where: `story/journey_history.py:227` `if generated and len(memory.split()) < _GENERATED_MEMORY_FLOOR_WORDS:`
  (floor 30, :37); `:356-357` `raise ValueError("generated journey returned fewer than three usable events")`.
  Same class as `world/charter_history.py:575` (reported by the charter audits; this sibling was flagged there
  as unverified).
- Snippet (under `language_scope('ja')`, a 97-character first-person Japanese memory, four events):
  `kept 0 dropped [{... 'reason': 'thin_memory'} x4]`, `words by split: 1`.
- Fix: measure in the pack's units — the same `linguistic(...)` posture the first-person check two lines above
  already uses (a pack-scoped minimum, e.g. characters for `ja`), never whitespace words.
- Test: `ground_journey_history` in `ja` with a long first-person memory keeps it.

### F10 — Every non-person source of a report is renamed "the unfamiliar person" before it reaches the mind
- Severity: **WRONG-SCENE** (and a floor that subtracts more than its rule: provenance "read on a wall" becomes
  "a stranger said"). Confidence: **CONFIRMED** (snippet).
- Where: `agents/character.py:3475-3478`:
  ```
  if teller and not _recognizes(teller, known):
      shown = str(label(teller) or "").strip()
      report["told_by"] = (shown if shown and shown != teller
                           else _unknown_actor_label(teller))
  ```
  `label` returns non-person text unchanged (`agents/common_identity.py:189-207`), so `shown == teller` and the
  voice is replaced. The carrier modules write voices deliberately as "a source a mind can weigh"
  (`couriers.courier_voice` :226-236, `artifacts.artifact_voice` :95-105, `crowds.crowd_voice`).
- Snippet: `tellers_as_known` over `told_by` = "a wanted bill nailed to the post" (`provenance: read`),
  "a rider", "the crowd in the square" -> all three `the unfamiliar person`.
- Fix: carry the teller's kind on the row when it is written (person vs crowd/courier/artifact — the writer
  knows) and relabel only persons; never infer it from the string.
- Test: a read copy from an artifact keeps its voice in the payload; a told copy from an unmet person is
  relabelled.

### F11 — A courier crossing several edges in one sweep pays the FIRST edge's price for all of them
- Severity: **WRONG-SCENE**. Confidence: **CONFIRMED** (snippet).
- Where: `story/couriers.py:389-390` (`pace = courier_edge_seconds(scene, route[leg], route[leg + 1], pace)`
  computed once, before) the loop `:391-403` that advances many legs with that one `pace`.
- Snippet (edge costs stubbed; per-edge courier cost `[45.0, 600.0, 600.0, 600.0]`, walking):
  `advance_couriers(..., 200.0)` -> `after 200s: e arrived moved_at 180.0 moves 4` — 1,845 s of road crossed in
  180 s. The reverse ordering slows him by the same error. A time skip is exactly when a sweep crosses many
  edges.
- Fix: recompute `pace` per leg inside the loop (`courier_edge_seconds(scene, here, nxt, flat)`).
- Test: two-edge route, cheap then dear; a clock covering only the cheap edge plus part of the dear one moves
  one leg.

### F12 — A caravan carried through a stop in a skip picks up what happened there after it left
- Severity: **WRONG-SCENE** (information outruns its carrier). Confidence: **PLAUSIBLE** (traced).
- Where: `story/couriers.py:700-718` (`for row, payload, witnessed in surfaces(room)` — no bound on
  `occurred_at`), `:720-748` (bills posted since), `:661-693`/`:750-777` (the crowd standing there now).
  `advance_couriers` knows when each stop was left (`moved_at` at :398-403) but `stops_due` keeps only the leg.
  The docstring (:617-621) names the approximation; it does not name the time travel.
- Scenario: an 8-hour skip; the wagon halts at the market at hour 1 and arrives at the gate at hour 3, all
  in one sweep; an event at the market at hour 7 (fired this beat, `occurred_at` within the skip) boards the
  wagon and is delivered at the gate.
- Fix: record `(leg, left_at)` in `stops_due` and offer only surfaces with `occurred_at <= left_at` (and bills
  posted before it); the crowd exchange the same.
- Test: a surface stamped after the stop's departure is not in the cargo.

### F13 — Era-shared couriers, crowds, notices and the frontier's ledgers are driven by each frame's own clock and scene
- Severity: **WRONG-SCENE**. Confidence: **PLAUSIBLE** (traced; not executed across frames).
- Where: `core/db.py:160-171` (`ERA_WORLD_KEYS`: `crowds`, `couriers`, `artifacts`, `room_frontier`, ...) vs
  `simulation_clock`/`scene` frame-scoped (`FRAME_SCOPED_WORLD_KEYS`); `story/couriers.py:830-837` reads the
  committing frame's clock; `:1125-1126` walks that frame's `passable_neighbors(scene)`;
  `story/room_frontier.py:469,492,507-511,545-549` stamp and compare `elapsed_seconds` of whichever frame
  calls. Bubble clocks do diverge (`world/spatial_frames.py:1700-1712`, "Reunion clock skew").
- Scenario: the away party (a spatial bubble) skips six hours; its commit advances the era's rider — dispatched
  by the home party five minutes earlier — to his destination and delivers; the home frame, clock unmoved,
  never sees him ride. Conversely a parent clock behind `moved_at` freezes every courier. In `fills_this_hour`,
  `now - elapsed` is negative for fills stamped by a frame ahead, and negative counts as "this hour", so the
  slower frame's fill line reads spent.
- Fix: stamp era-shared rows with the ERA's clock (or move each courier on the max of the era's frame clocks,
  once per era), and resolve rooms against the era's map, as the charter does for town events
  (`_scheduled_row` "THE TOWN'S EVENT, NOT THE BUBBLE'S").
- Test: two frames of one era with skewed clocks; a courier advances once, by the era clock.

### F14 — The planting sketch reads a join's barrier out of free prose with an ASCII, English-ordered reader
- Severity: **WRONG-SCENE** (+ language-pack hazard). Confidence: **CONFIRMED** for the reader's outputs,
  **PLAUSIBLE** end to end.
- Where: `story/room_sketch.py:667-684` (`_edge`: `barrier = normalize_barrier(way, unresolved=unread)`;
  `if not unread and barrier != "wall": edge["barrier"] = barrier`). The card asks for `way` as free words
  ("how one gets there from that room", `room_sketch.txt` line 6), never a barrier; `normalize_barrier`
  folds `[^a-z0-9]` (`world/spatial_barriers.py:331-400`).
- Snippet: `'鍵のかかった鉄の門' -> wall UNREAD`, `'細い石段' -> wall UNREAD` (both become an OPEN join);
  `'the bolted cellar door' -> wall` (read, then discarded by `!= "wall"` -> open); `'a barred gate' -> open`;
  `'through the window' -> window`. In a Japanese story every sketched join is an opening — a room reached
  through a window becomes walkable (Home 9's class, `room_slice.room_graph` docstring).
- Fix: ask the sketch for the barrier in the engine's closed vocabulary (the field `plan_rooms` takes) and keep
  `way` as the label only.
- Test: a sketch answer with a Japanese `way` and `barrier: "window"` files a `window` edge.

### F15 — Two "when" units on one field: spoor reads carry charter HOURS in `occurred_at`, and invented claims carry 0.0
- Severity: **WRONG-SCENE**. Confidence: **CONFIRMED** (stored values) / **PLAUSIBLE** (voice effect, traced).
- Where: `story/artifacts.py:411` (`"occurred_at": float(row.get("at_hours") or 0.0)`) — snippet: the stored
  spoor report holds `52.5` (hours) where every other envelope holds simulation seconds;
  `story/carriers.py:1129` (`_invented_claim`: `"occurred_at": 0.0`), copied on every retelling
  (`:1337`, `couriers.py:449`, `artifacts.py:165`). `world/charter_news.py:245-249` treats a non-None value as
  seconds (`charter_hours_of`), so both land at story second ~0; `world/charter_log.py:350-352` tells a charter
  voice `hours_ago = clock_hours - happened_at`.
- Scenario: a lie told to a townsperson at hour 50 of the story reaches that body's voice as news 50 hours old;
  a carcass read by a caravan rides as news from the story's opening.
- Fix: spoor converts with `sim_seconds_of(at_hours, anchor)`; an invented claim stamps the simulation second
  it was said (or None, letting the receiver stamp acquisition).
- Test: an invented claim told to a charter body has `happened_at` equal to the charter hour of the telling.

### F16 — Carcasses are sent to the notice-wording mint
- Severity: **WRONG-SCENE** (+ spend). Confidence: **CONFIRMED** (read).
- Where: `story/artifacts.py:501-505` (pending = every `POSTED` artifact with no text — spoor included, it is
  posted by `spoor_artifact` :398-418 with `text: ""`); the card asks for "the actual words on the paper"
  (`artifact_wording.txt`); `agents/director_views.py:672-686` hands the Director `text`, "what the prose may
  quote".
- Scenario: a deer carcass in the glade gets minted wording ("WARNING: ...") which the Director may quote as
  writing on it; each spoor costs up to 2 jobs x 2 calls.
- Fix: exclude `spoor` from `pending`.
- Test: a standing spoor is not scheduled for wording.

### F17 — A grant listing more than 24 capabilities is silently cut to 24 when stored; the caller is shown the uncut row
- Severity: **SILENT-NOOP**. Confidence: **CONFIRMED** (snippet).
- Where: `story/room_conversation.py:235-236` (`normalize_mandate`: `"capabilities": [...][:24]`), applied by
  `story/mandates.py:380-382` (`_save`); `grant_mandate` returns the pre-normalized `row` (:479). The vocabulary
  has 34 members (`MANDATE_CAPABILITIES`).
- Snippet: a grant enumerating 33 kinds -> `returned caps 33 stored caps 24`, dropped on save:
  `director_note, place_at_opening, move_body, assign_post, plant_claim, adjust_stock, arm_trigger,
  charter_shock, region_events`; `permits(stored, 'region_events') -> False`. A Planner that enumerates "full
  authority" (the register says it still may, UNBUILT_PLANNING F15) loses the tail without a word.
- Fix: drop the `[:24]` (the vocabulary is closed and validated at grant) or size it from
  `len(MANDATE_CAPABILITIES)`; return the stored row.
- Test: grant every capability by name; each permits after a reload.

### F18 — The same sentence in the same scope is "one grant" even when it grants something else
- Severity: **SILENT-NOOP**. Confidence: **CONFIRMED** (snippet).
- Where: `story/mandates.py:457-461` (match on `text` + `scope` only; returns the existing row).
- Snippet: `grant("Yes, go ahead.", ['arrival'], request='pkg_courier')` then
  `grant("Yes, go ahead.", ['plan_rooms'], request='pkg_tower')` -> `same row returned: True | rows stored: 1`,
  `plan_rooms permitted: False`, request still `pkg_courier`. Short assents are the commonest grant sentence.
- Fix: dedupe on (text, scope, capabilities, request); a different ask is a new row.
- Test: the snippet's two grants -> two rows, both permitting what they named.

### F19 — Standing spoor fills the notice cap: eight carcasses forbid every bill
- Severity: **SILENT-NOOP**. Confidence: **CONFIRMED** (snippet).
- Where: `story/artifacts.py:259-263` (`sum(1 for a in artifacts if a.get("status") == POSTED) >= MAX_ARTIFACTS`
  counts spoor) against its own note `:392-395` ("must not compete for the same eight slots").
- Snippet: eight spoor posted -> `posted spoor: 8 MAX_ARTIFACTS 8 -> run_artifacts post gate: True`.
- Fix: count `not a.get("spoor")` in the notice cap.
- Test: eight spoor standing, a post succeeds.

### F20 — A courier addressed to nobody the story holds waits at the gate forever, holding one of six road slots
- Severity: **SILENT-NOOP** (resource leak in world state). Confidence: **CONFIRMED** (read).
- Where: `story/couriers.py:1015-1016` (`courier["addressee"] = " ".join(...)` — never validated);
  `:544-547` (`if entry is None or entry.get("room") != room: return courier, ...` — status stays `ARRIVED`);
  `:948-952` (`MAX_COURIERS` = 6 counts `ARRIVED`); no expiry anywhere.
- Scenario: the encoder writes `addressee: "the Baron"` where the cast holds "Baron Aldric Venn"; the rider
  arrives and stands forever; six such and no courier can ever be sent. A route held by a door that never reopens
  is the same shape (`advance_couriers` :394-395).
- Fix: refuse a send whose addressee resolves to no carrier; give an `ARRIVED` courier a bounded wait in story
  time (an owner's number) after which he tells the place or turns back.
- Test: dispatch with an unknown addressee -> refused with a reason.

### F21 — Notice wording: a bare `json.loads` on model output, and a duplicate job every beat while a bill is blank
- Severity: **SILENT-NOOP** (+ spend). Confidence: **PLAUSIBLE** (fences) / **CONFIRMED** (job key).
- Where: `story/artifacts.py:570` `out = json.loads(chat_complete("utility", sys, user, ...))` — no fence strip
  or salvage (`agents/common_llm.jparse`, :139, exists for this; sibling of the class at UNBUILT_PIPELINE 1.214,
  which names only the Room). `:541-544` job key `"artifact_wording:t%d:%s" % (turn_idx, uids)`: `core/jobs.submit`
  dedupes on the exact key (:114-123), so each beat while a job is in flight starts another for the same bills;
  with a failing provider both jobs count failures and `_WORDING_ATTEMPT_CAP` (2) is spent in one window, leaving
  the bill plain forever.
- Fix: parse with `jparse`; key the job on the uids alone.
- Test: a fenced ```json answer lands; two schedules in consecutive beats join one job.

### F22 — A grant's term is counted in turns of the whole chat, every era included
- Severity: **SILENT-NOOP** (a licence lapses early). Confidence: **PLAUSIBLE** (traced).
- Where: `story/mandates.py:391-393,450,491` (`_turn_now` -> `room_conversation.current_turn_idx`:
  `SELECT MAX(idx) FROM turns WHERE chat_id=?`, `story/room_conversation.py:216-218`) against `expires_turn`
  (:497-498); `room_mandates` is an ERA key, so a past/future era's beats spend the present era's term.
  `room_frontier.frame_turn_idx`/`_other_frames_beats` (:645-665) exist for this correction and are not used.
- Fix: count a grant's term in its own era's beats (the frontier's helpers).
- Test: a grant expiring in 2 beats survives 5 beats played in a flashback frame.

### F23 — `close_request` and `renew_mandate` have no production caller
- Severity: **DEAD**. Confidence: **CONFIRMED** (grep: only `tests/test_mandate_scope_and_totality.py`).
- Where: `story/mandates.py:512-537`, `:540-561`. No Room tool (`story/room_tools.py` TOOLS), no route, no Planner
  output field reaches them; Design.md:403 describes both as built seams. A grant scoped to an `other` ask
  ("endable only by someone saying so") can only be revoked whole in the panel.
- Fix: expose them (a Planner output key or a Room tool), or say in Design.md that they are test-only.
- Test: a Planner reply that withdraws an ask lapses the grant scoped to it.

### F24 — The player fallbacks in the courier and notice ops are unreachable, and their comments contradict the persona carrier
- Severity: **DEAD** (+ stale comment). Confidence: **CONFIRMED** (`ChatData.get` exists,
  `core/pipeline_context.py:299`, so `persona_entry` puts the player in `_cast_index`).
- Where: `story/couriers.py:1084-1088` ("The player's own knowledge is the transcript"), `:865-866`;
  `story/artifacts.py:347-351`, `:223-224`. Since 0bed7cf the persona holds reports (`carriers.py:69-91`), so the
  `listener is not None` branch always wins.
- Fix: delete the branches or reduce them to the bare-namespace case with a comment saying so.

### F25 — `reports_for_state` says "newest first"; it returns the newest few in chronological order
- Severity: **STALE-DOC**. Confidence: **CONFIRMED**.
- Where: `story/carriers.py:132` docstring vs `:150` `rows[-cap:]`. `world/crowds.talk_view` corrected the same
  sentence about the same slice ("Which is not 'newest first', as this said for two releases").
- Fix: correct the docstring (the order is right for a mind).

### F26 — The wording spend is documented as gated by the off-screen ceiling; it was ungated on 2026-09-20
- Severity: **STALE-DOC**. Confidence: **CONFIRMED**.
- Where: `persist/commit.py:887-890` ("gated on the ceiling setting"), AGENTS.md:443 ("its optional spend is
  governed by the `stochastic` off-screen ceiling"), `story/artifacts.py:35-42` module note, vs
  `story/artifacts.py:493-500` ("UNGATED 2026-09-20").
- Fix: correct the three texts.

### F27 — AGENTS.md states room spend defaults the code removed
- Severity: **STALE-DOC**. Confidence: **CONFIRMED**.
- Where: AGENTS.md:483 ("`spend_limits`: `CALLS_PER_REPLY` = 60 / cap 200, `CALLS_PER_STORY_HOUR` = 240 / cap
  1200") vs `story/mandates.py:163-172` (all four `None`, owner 2026-10-01/03). The planner audit reported the
  same stale number in DESIGN_ROOM_PRELUDE; this is the routing table's copy.

### F28 — `location_design`'s module note says the draft is cleared whatever happens and never read afterwards
- Severity: **STALE-DOC**. Confidence: **CONFIRMED**.
- Where: `story/location_design.py:28-30` vs `pause_draft`/`resumable_draft` (:122-162) and their caller
  `agents/story_planner.py:2141-2150` (a wall-stopped pass is kept and resumed).

### F29 — `room_proposals` documents `revised` as "revised, awaiting the Planner"; the code means "sent back, awaiting the Dramaturge"
- Severity: **STALE-DOC** (with a behaviour edge). Confidence: **CONFIRMED** (read).
- Where: `story/room_proposals.py:12-13` vs `judge_proposal` (:355-356 sets `revised` on a revise verdict) and
  `revise_proposal` (:375-380 sets `open` after revising). `PENDING_STATUSES` (:61) counts `revised` as awaiting
  the Planner, so a revision whose Dramaturge call failed is re-judged unrevised at the next deliberation.
- Fix: correct the note; treat `revised` as awaiting the Dramaturge in `awaits_planner`.

### F30 — An unknown mandate status normalizes to `active` (a licence by default)
- Severity: **SILENT-NOOP** (fail-open). Confidence: **PLAUSIBLE** (no current producer of another status; an
  archive from a later build is one).
- Where: `story/room_conversation.py:227-229` (`if status not in MANDATE_STATUSES: status = "active"`). The
  mandate model's own rule is "silence is never permission". Same shape at `room_proposals.py:122-124`
  (unknown -> `open`).
- Fix: unknown -> `expired` with a lapse reason.

### F31 — `PROPOSALS_CAP` can evict an accepted proposal that is still being built
- Severity: **SILENT-NOOP**. Confidence: **PLAUSIBLE**.
- Where: `story/room_proposals.py:259-264` evicts any row `not awaits_planner(p)`, `accepted` included, while
  `:62-66` says an accepted proposal "is still being worked and may still be waiting on a grant".
- Fix: evict only `SETTLED_STATUSES` (and `quiet`).

### F32 — `room_slice.cast_rooms` is a second body predicate beside "the one body predicate"
- Severity: **WRONG-SCENE** (author map ordering only). Confidence: **PLAUSIBLE**.
- Where: `story/room_slice.py:330-348` (entity kind by exact positions key; no ledger tier) vs
  `world/spatial_identity.scene_names_body` (:343), which `room_slices` itself uses (:482-487). A thing whose
  positions key differs from its entity key counts as a body here, so its room ranks as a cast room (hops 0).
- Fix: `cast_rooms` calls `scene_names_body`.

### F33 — English glue inside model-facing world text and an inline English prompt
- Severity: **WRONG-SCENE** (language pack, low). Confidence: **CONFIRMED** (read).
- Where: `story/room_sketch.py:1036-1038` (`"%s (at %s)" % (summary, name)` written into a `schedule_event`
  summary the Director reads); `story/journey_history.py:39-92` (`_SYSTEM`, an English prompt outside the
  language packs, with an English connective list "no 'Later', no 'Early on' ..."); `language_packs/ja/.../
  artifact_wording.txt` keeps an untranslated `'several'`.
- Fix: route the glue and the prompt through the pack.

### F34 — Crowd rows are read under an explicit frame and written back under the ambient one
- Severity: **CORRUPTION** (latent; correct inside a pipeline run). Confidence: **PLAUSIBLE**.
- Where: `story/carriers.py:1206` (`_crowd_index(cid, frame_id)` — "THE FRAME IS READ, not merely accepted")
  vs `:1360-1368` (`wget`/`wset` ambient); `:358-360,387` (`_crowds_acquire`); `story/couriers.py:830-837,
  1129-1131,1164-1167`; `story/artifacts.py:112,202,382`. Any caller outside a pipeline run with a different
  ambient frame merges one era's crowds into another's.
- Fix: thread `frame_id` through every read and write (`wget_for_frame`/`wset_for_frame`).

## Efficiency

1. **The carrier index is rebuilt by `run_couriers`/`run_artifacts` on beats that need no index** —
   `story/couriers.py:839`, `story/artifacts.py:205` build `_cast_index` unconditionally; any acquisition earlier
   in the beat bumped `_LEDGER_WRITES` (`carriers.py:475`), so the memo misses and the whole walk reruns — the
   module's own measurement is 45 ms a rebuild on chat 114, 30 ms of it `charter_runtime.carrier_entries`
   (`carriers.py:536-538`) — plus a deepcopy of every carrier's ledger (`_private_entries`, :497) even on a hit.
   Hot: every beat, in the commit transaction. Fix: return early from `run_artifacts` with no ops and skip the
   index in `run_couriers` when there are no ops and no live couriers; patch the memo with the written entry
   instead of invalidating it globally. Expected: ~45 ms/beat on a large town, 0 elsewhere.
2. **`names_nobody_holds` rescans the whole frame's Director output on every Room payload build** —
   `story/carriers.py:895-911` (LIKE over every `director_resolve`/`director_establish` variant, then
   `json.loads` of each match). Runs when any claim is near (`:1036-1040`), from `story_planner._claims_near`
   (memoized per reply but dropped by every write and every landed beat) and `room_sketch.sketch_payload`. O(turns)
   blobs per call; a long story's write-heavy reply pays it per step. Fix: collect `introductions` heads at commit
   (`commit_mapping` already reads that field) or memo on `core.db.db_read_token()`.
3. **Mandate reads re-sweep and re-parse the package ledger every time** — `story/mandates.py:628-632`
   (`active_mandates` calls `expire_mandates` on every read), `:352-358` (`request_open` -> `get_package` ->
   `plot_packages.packages`, a parse + normalize of the WHOLE ledger per package-scoped grant). `sketch_payload`
   calls `coverage` about eleven times (`room_sketch.py:471-485`); the commit tail and every planner step add
   more. Fix: sweep once per caller (pass the active rows into `coverage`), parse the ledger once per sweep.
4. `schedule_artifact_wording` starts a duplicate job per beat per blank bill and words carcasses (F16, F21) —
   per beat while any bill is blank; 2 calls per job.
5. `advance_carriers` issues one SELECT per fired event (`carriers.py:219-222`) and one per distinct carrier room
   (`standing_surfaces_reader`, :183-187); with every unbound charter body a carrier that is tens of rooms a beat.
   One `IN (...)` query and one windowed query over the rooms would do.
6. `unbacked_claims` calls `_carriers` with no ctx (`carriers.py:1018`), a full rebuild (registry walk) per payload
   build; `couriers._exchange_stops` re-reads and re-parses the artifacts row per stop per caravan (:723-724).

## Already registered

- `room_sketch._ask` parses the answer with `jparse` — UNBUILT_PIPELINE §1.214 ("The Room reads a whole answer
  with plain `json.loads`").
- A frontier stub's join type; the Room's map (`room_slice`, `structure.planned_topology`) counting a far join
  as a hop — UNBUILT_WORLD §1.228.
- Sketch residuals (local events ride only a planting question; spend records one call; escalation rate
  unmeasured; claimed persons handed on repeatedly) — UNBUILT_PLANNING (planting-sketch entry, ~445-462; claims
  entry ~77-82).
- The claim heads (`_name_head`, `_said_whole`) are only as precise as the encoder's `learns` — UNBUILT_PLANNING ~81.
- "The Planner has to write `everything`" and "pass `request` ... offer to close the request" — UNBUILT_PLANNING
  ~747-760 and ~988-997 (F23 above adds that no seam exists to close one).
- Every interpret builds the carried-reports view (Director payload cost) — UNBUILT_PIPELINE item 9 (~126).
- Courier edge pricing as a multiplier over the room's crossing — UNBUILT_LIVING_WORLD §1.142 (the per-sweep
  pricing bug F11 is not in it).

## Structure notes

- `story/carriers.py` holds four seams: acquisition (`standing_surfaces_reader`, `advance_carriers`,
  `_crowds_acquire`); the carrier index (`persona_entry`, `save_state`, `_carriers`/`_build_carriers`,
  `_cast_index`); tellings (`apply_tellings`, `_invented_claim`, `_crowd_index`); and the Writers' Room's claims
  reader (`unbacked_claims`, `names_nobody_holds`, `_held_identity_roster`, `_name_head`, `_said_whole`, the
  `ROOM_CLAIM*` caps), which is author-layer and imports `persist.commit`/`agents.common` — a clean
  `story/claims.py`. `apply_tellings` (200 lines) is a monolith in miniature.
- `story/couriers.py`: the pure route model (`new_courier`, `advance_couriers`, `carried_bundle`, `_copy_of`) vs
  `run_couriers` (805-1170, three ops + sweep + exchange + delivery in one function — a monolith in miniature).
- `story/artifacts.py`: the spoor block (`spoor_artifact`, `post_spoor`, `SPOOR_STANDING_CAP`) is the charter
  creature's and shares only the shape; the wording ceiling is a separate seam.
- `story/room_sketch.py`: `sketch_payload` (~260 lines) and `_plan` (~240 lines) are monoliths in miniature.
- `story/room_proposals.py`: the restore bookkeeping (`held_briefs`, `keep_briefs`, `held_rows`, `keep_spared`,
  ~180 lines) is its own seam.
- `story/mandates.py`: the free hand and the spend block are separable.
- Module-level mutable state: `story/carriers.py:64` `_LEDGER_WRITES` (writer: `save_state`, `global` +=; read
  by `_carriers`); `story/room_conversation.py:349` `PLANNER` (writer: `seat_planner`, `global` rebind — no
  module imports the name, so the rebind is seen). Two stores of one fact: spoor (registry vs artifact status,
  F7); a courier's position (`at` vs `route[leg]`, kept consistent by `advance_couriers`); the returned vs stored
  mandate row (F17); `occurred_at` units (F15).

## Docs checked

- AGENTS.md:443 "Only a non-empty public `witnessed` surface may enter a carrier, and only that holder's private
  payload reads it" — holds for the ledger; crowd-held surfaces also reach every observer in the crowd's room as
  `talk` (by design, `common_rooms.py:142-156`). "Later arrivals at still-standing surfaces" — holds, but nothing
  tells a standing surface from a passing act (F3). "a courier ... unable to deliver once silenced" — holds.
  "its optional spend is governed by the `stochastic` off-screen ceiling" — FAILS (F26).
- AGENTS.md:483 spend defaults — FAILS (F27). "An unknown capability is refused at the grant, so a row means
  exactly one thing" — holds at the grant, FAILS on save past 24 (F17). "the withdrawal is shown to the Planner on
  its next reply" — holds only when that reply is within about two beats (`revoked_since`, :800-809).
- Design.md:402 "the room acts under nothing else" — holds for packages (authority checked at validate and
  publish); a lost revocation (F5) breaks it under a race.
- Design.md:403 "`close_request` called outright ... Renewal ... (`renew_mandate`)" — the functions work but
  nothing calls them (F23); "What is left is the Planner passing the request" — STALE: `_apply_grants` passes it
  (`agents/story_planner.py:870`).
- Design.md:404 "an ENUMERATED grant still covers exactly what it listed" — FAILS past 24 (F17).
- Design.md:270 "A crowd, a courier and a posted notice reach the minds in the room" — holds.
- `story/carriers.py` module note "No timer grants knowledge, no prose is generated" — holds; "only physical
  holders at that location acquire it" — holds, without a consciousness test (F2).
- `story/couriers.py` module note "a rollback un-sends the rider" — holds (`commit_information_carriers` runs in
  one domain inside the outer transaction, `persist/commit.py:556,636-639`; the registry session flushes inside it,
  :681; `_commit_domain` re-raises, :482-488). The "one commit domain" requirement holds for tellings, couriers
  and notices; it does not cover the out-of-band wording landing (F4).
- `story/room_frontier.py` `_update` docstring (the four-writer lost-update analysis) — holds for this row;
  `room_mandates` has the same writers and no such guard (F5).
- `story/room_slice.py` "Neither writes anything" — holds. `story/room_calls.py` "adds no retry, no repair" —
  holds.
- `story/room_research.py` "Every query and every page address is written into the room thread ... BEFORE it
  leaves the machine" — holds (`_disclose` precedes `rp.search`/`rp.fetch`).
- UNBUILT_PLANNING (planting sketch) "a sketched room carries a name, a purpose and the way it joins, never
  geometry, exposure or level" — STALE: `_seen_from_afar` now carries `exposure` and `far_look`
  (`room_sketch.py:687-706`).
