# Audit — the non-spatial half of `world/`

Status: working notes. Evidence, not authority. Companion to
[`AUDIT_SPATIAL.md`](AUDIT_SPATIAL.md), which covered the thirteen
`spatial_*` modules of the same package last week; nothing here re-audits
those, though every claim below about how this half USES them was checked
against their source.

Scope: `offscreen.py` (2125), `weather.py` (808), `living_world.py` (608),
`crowds.py` (608), `gaps.py` (542), `place_purpose.py` (532), `paradox.py`
(489), `background_claims.py` (466), `subjects.py` (449), `survival.py` (320),
`mechanics.py` (310), `comfort.py` (306), `routines.py` (200),
`degradation.py` (171) — 7,944 lines, read end to end.

This is the world that runs whether or not the player is looking at it:
offscreen simulation, weather, crowds, scheduled consequences, the gap-filling
narrator for time nobody watched, and unratified background claims.

**Nothing here was fixed. Flag, never fix.** Line numbers are as of
`4f33b17` (alpha 9.5+). Dead-symbol claims were verified by whole-repo grep
(`-w`, all `*.py`) with `tests/` counted separately from production, because
in this package a symbol with only test callers is the commonest shape of
dead code. Live-corpus figures were read from `engine.db` opened
`mode=ro`; the database was never written.

---

## Findings

Format: claim · evidence (`file:line`) · why it matters.

### Dead code, and guards whose condition can no longer be true

**F1. The gap-filling narrator cannot run.** `gaps.gap_for` chooses its rung
at `gaps.py:414` — `effective = "low" if (resolution == "low" or derived ==
"low") else "medium"` — and **both** production callers pass
`resolution="low"`: `gaps.interim_for` (`gaps.py:536`, "Asks for `low`
explicitly") and `offscreen.profile_summary_record` (`offscreen.py:1124`).
Verified: those are the only two `gap_for(` call sites outside `tests/`. So
`_medium_overlay` (`gaps.py:328-375`), the `_MediumFallback` class, the
one-retry loop, the room-roster gate, the `fell_back_from` record and the
`gap_medium` system prompt shipped in **two language packs**
(`language_packs/en/cards/system_prompts.json:69`,
`language_packs/ja/…:69`) are all unreachable in production. This is the
module's entire model-priced half. It matters because `gaps.py`'s docstring
sells the two-rung design as the module's shape ("`medium` adds one bounded
call over that deterministic skeleton"), and a reader costing the feature
will price a call that never happens.

**F1a, and it is not free.** `_derived_resolution` (`gaps.py:109-130`) runs
unconditionally at `gaps.py:413`, BEFORE the line that discards its answer.
It walks `extant_cast` and `json.loads` every cast sheet to decide a tier
that cannot change the outcome. `interim_for` is called once per character
per beat from `agents/character.py:3135` — so this is a full cast scan per
character per turn, on the turn path, for a value structurally guaranteed to
be ignored.

**F2. `weather._MUFFLING`'s `else` clause is unreachable.**
`weather.py:476-481` walks `_MUFFLING` (limits `0, 1, 2` at `weather.py:325-330`)
and falls through to `muffling, gain = "faint", …`. The loop is only entered
when `audible` is true (`weather.py:473`), which requires `layers <= reach`,
and `max(_REACH.values()) == 2` (`weather.py:320`) — the last `_MUFFLING`
limit. Confirmed by evaluating both tables. The `for…else` reads as a
defence against a deeper room and is a no-op; if `_REACH` ever gains a rung
the fallback is what *would* fire, so it is a live-looking guard that is
currently proof of nothing.

**F3. `mechanics._fire_due_events` counts two things nobody receives.**
`mechanics.py:130` initialises `fired = news_fired = consequences_fired = 0`
and `mechanics.py:204-207` returns all three in `counts` — but
`mechanics_sweep` reads only `counts["fired"]` (`mechanics.py:300`, the
dock-edge gate) and **does not return `counts` at all**
(`mechanics.py:310`). The sole caller, `persist/commit_mechanics.py:83-110`,
recomputes `news_fired` and `consequences_fired` itself from `event_ops` and
its own `kind_by_id` map. Two counters, two implementations, one of them
discarded on every sweep. This is the "two representations of one rule"
shape at its cheapest: the day the two disagree, the surviving one is the
copy in the commit domain and nothing will say so.

**F4. `weather.severity_intensity_cap` has no caller anywhere but its own
test.** `weather.py:801-808`. Verified: the only non-test reference in the
repository is the definition. Its docstring states a rule — "The worst this
story's sky is allowed to drift to" — that nothing enforces: `advance_weather`
(`weather.py:656`) takes no severity argument and applies no cap. See F11 for
the setting this leaves inert.

**F5. `crowds.apply_ops` has a dead assignment.** `crowds.py:328`:
`target = by_uid.get(uid)` is immediately followed by `continue` at
`crowds.py:331` with `target` never read again. Harmless; it reads as though
the `emerge` branch falls through into the shared edit path, and it does not.

**F6. `survival`'s air guard cannot be false.** `survival.py:235`:
`seconds / _AIR_SECONDS if _AIR_SECONDS else 0`, against
`_AIR_SECONDS = 900.0` at `survival.py:92` — a module constant that has never
been zero and has no writer. Trivial, but it is the only division guard in the
file and it protects nothing.

**F7. `paradox` computes a stage nothing implements, then undoes it.**
`_stage_for` (`paradox.py:240-245`) walks five `STAGE_THRESHOLDS`
(`paradox.py:74`) and can return `4`. `_apply_hazard_stage` handles `>= 2` and
`>= 3` only (`paradox.py:257, 261`); `_apply_warden_stage` handles `>= 1`.
Stage 4 requires `severity >= 1.0`, and `_advance_paradox` applies the stage
consequence at `paradox.py:410` and then, four lines later
(`paradox.py:412-421`), force-restores the anchor, calls `_restore_consumed`
and clears the paradox. So the top rung of the ladder is applied and reverted
inside one call. Either the ceiling should not apply a stage or the ladder has
four rungs, not five.

**F8. `check_and_apply_paradox(ctx, nonce)` never uses `nonce`.**
`paradox.py:440`; verified by reading the whole body (`440-489`). It is passed
by `persist/commit.py:387` as the domain's idempotency token, which is what
every other commit domain uses it for. (`spatial_frames.detect_and_reconcile_spatial`
takes and ignores the same argument — noted for parity, not audited here.)

### A configurable value nothing reads

**F9. Three of the four `weather_severity` values are indistinguishable in the
engine.** `story/scene.py:1844` declares `("calm", "seasonal", "harsh",
"catastrophic")` and the setting is host-facing
(`static/js/settings.js:96, 210`). Its only engine consumer is
`weather.ground_after` (`weather.py:753`, via `commit_scene_state._advance_ground`
at `persist/commit_scene_state.py:195-201`), and the only branch that reads it
is `if severity == "calm"` (`weather.py:768`). `harsh` and `catastrophic`
behave exactly as `seasonal` everywhere in the world model. The value does
reach the browser overlay (`web/app.py:5489` →
`static/js/weather-fx.js:257`), so the setting changes how hard the *particles*
fall and nothing about the sky, the ground, or what any mind can perceive.
The function that would have made it matter is F4.

**F10. `offscreen.agent_context` reads a character-state key that no writer
produces.** `offscreen.py:1582`: `"beliefs": state.get("beliefs") or {}`.
Beliefs are written to `state["interior"]["beliefs"]`
(`persist/commit_memory.py:1278-1282`, inside `_interior_out`), and read from
there everywhere else (`agents/character.py:2408, 2852`). Measured on the live
database: **0 of 85 `chat_chars.state` rows carry a top-level `beliefs` key**
(the keys present are `stance`, `active_state`, `mind_models`, `interior`,
`recent_tells`, `tell_grounds`, `active_hypotheses`, …). So the paid
full-agent rung — the one the design calls "the highest-fidelity purchase" —
always receives `beliefs: {}`. `AGENT_CONTEXT_KEYS` documents the field as
"what they think is true, including wrongly" (`offscreen.py:1520`), and
`mind_models`, the actual belief store, is not read at all. This is the
package's signature failure shape: an allowlist that lists the right field and
reads the wrong key fails silently and looks measured.

(Adjacent, same function: `state.get("last_known")` at `offscreen.py:1587` is a
second key nothing writes — it is a fallback behind
`state["offscreen_agent"]["last_known"]`, which `land_agent_tick` does write,
so this one is merely inert.)

### A list kept in sync by hand, and not

**F11. `place_purpose._HERE_LEXICON["rest"]` claims parity with `comfort` and
is missing 18 of its tokens.** `place_purpose.py:154-156` says the soft-support
and warmth sets "are in parity with comfort.py's vocabulary". Computed
difference: the warmth sets are identical; the rest set is a strict SUBSET of
`comfort._SOFT_TOKENS` (`comfort.py:62-69`) missing `armchair(s)`,
`blanket(s)`, `cushion(s)`, `cushioned`, `featherbed(s)`, `fur(s)`,
`pillow(s)`, `pillowed`, `quilt(s)`, `settee(s)`. Consequence: a body on a
featherbed gets ambient comfort and passive stamina recovery
(`comfort.comfort_level`, `survival.tick_vitals:242`) while the room it is in
reports no `rest` affordance to that same character's payload
(`place_purpose.here_affords`). Two lexicons, one subject, one of them
declared to be a copy of the other.

**F12. `here_affords` can never answer `shelter`.** `AFFORDANCES`
(`place_purpose.py:114`) has six members; `_NAME_LEXICON` grants `shelter`
(`place_purpose.py:134-150`) and `_CLAIM_LEXICON` recognises it
(`place_purpose.py:190`); `_HERE_LEXICON` (`place_purpose.py:157-178`) has
five keys and `shelter` is not among them. `here_affords`'s return
comprehension iterates `AFFORDANCES` (`place_purpose.py:260`), so one of the
six is structurally unreachable through the perception echo. Not a defect on
its own — there may be no honest structural token for shelter — but nothing in
the file says so, and the next reader adding an affordance has three lists to
find and no note pointing at the third.

**F13. `comfort._SUPPORT_MANNERS` omits the canonical manner for a supporting
surface.** `comfort.py:95-97` lists `rest, lean, press, touch, lie, sit, hold`
and its comment cites "spatial's `_CONTACT_KEY_MANNERS` vocabulary". The
canonical set is `spatial_contacts.CONTACT_MANNERS`
(`spatial_contacts.py:51-54`): `touch, hold, grip, press, rest, lean, wrap,
coil, straddle, pin, carry, **support**`. `support` — the one word in the
vocabulary that means exactly "this surface is holding this body up", and the
target of `_CONTACT_KEY_MANNERS`'s own `("support", "support")` mapping
(`spatial_contact_migration.py:47`) — is missing from the module whose entire
subject is supporting surfaces. Conversely `lie` and `sit` are in comfort's
set and in neither spatial vocabulary. The cited table is also the wrong one:
`_CONTACT_KEY_MANNERS` lives in `spatial_contact_migration.py`, is a
fragment→manner mapping, and is not the manner vocabulary.

**F14. `routines._SOCIAL_AFFORDANCES` is a hand-picked subset of
`place_purpose.AFFORDANCES`.** `routines.py:241` freezes
`{"food", "drink", "rest"}` and both `occupancy_fact` (`routines.py:288`) and
`entropy_facts` (`routines.py:322`) gate on it. It is derived from a list in
another module by hand, with no note in either file saying the two move
together.

### Two representations of one rule, free to drift

**F15. Crowds and the spatial layer disagree about how big a room is.**
`crowds.room_size_rank` (`crowds.py:85-89`) reads the raw authored
`RoomDef.size` string and falls to `medium` for anything else;
`agents/common.crowds_for_room` feeds it `room.get("size")` verbatim
(`agents/common.py:806`). `spatial_geometry.effective_room_size`
(`spatial_geometry.py:414-426`) answers the same question with a name/desc
keyword hint that promotes `hall`, `warehouse`, `plaza`, `courtyard`,
`atrium`, `cathedral`, `hangar` and ten more to `large`. So an unsized "Great
Hall" is `large` for proximity grading and `medium` for crowd density —
`density("a throng", ...)` returns `PACKED` under one and `CRUSH` under the
other, and `CRUSH` is what `terrain` turns into a `membrane` you cannot see
across and what `drift` turns into `CARRY`. `crowds.py:58-61` carefully
explains why it does NOT reuse `spatial._ROOM_COST`; it does not mention that
it also does not use `effective_room_size`, which is the function that exists
for exactly this grade.

**F16. `place_purpose.here_affords` restates the light→sight ladder as a
three-entry literal while claiming to use the caller's.** `place_purpose.py:229-231`:
`light = {"lit": "full", "dim": "partial", "dark": "none"}` then
`light.get(effective_light(...), "full") != "full"`. The docstring
(`place_purpose.py:221-222`) says it is "Gated on full sight (the
`_onward_exits` light rule)". `_onward_exits` does
`_LIGHT_SIGHT.get(effective_light(scene, target_id), "full") != "full"`
(`spatial_routing.py:738`) against the shared table at
`spatial_light.py:204-209`. The local copy omits `bright` — one of the four
`LIGHT_LEVELS` (`spatial_light.py:22`) — and only happens to be correct
because the permissive default catches it. It also invents a value
(`partial`) that appears in no other light vocabulary. The two rules are the
same today by coincidence and by a default, not by construction.

**F17. `gaps._skeleton` spells the `subject_last_seen` key twice, once by
constant and once by hand.** `gaps.py:68` defines `LAST_SEEN_KEY`;
`gaps.py:156` reads through it; `gaps.py:152` writes the literal string
`"subject_last_seen"` into the record's own `ledgers` provenance list. The
provenance is the thing a reader uses to know which ledger answered, so the
copy that drifts is the one that lies.

### Silent tolerance of empty, missing, or unknown values

**F18. `crowds.normalize_band` is the sibling of the room-`size` defect, and
worse.** `crowds.py:67-78` matches the whole casefolded string against four
multi-word phrases (`"a handful"`, `"a dozen or so"`, `"a few dozen"`,
`"a throng"`) and returns `BANDS[0]` for everything else. The field is
`CrowdOp.band: str = ""` (`llm/schemas.py:1667`) with the vocabulary in a
trailing COMMENT — so this is a model-written free string with no enum and no
synonym pass. "dozens", "a few dozen people", "several dozen", "a crowd", "a
throng of dockworkers" all become *a handful*. It is applied on mint
(`crowds.py:205`) and on every in-place edit (`crowds.py:384`), so a beat that
merely re-describes a throng shrinks it. And band drives everything: `density`
→ `terrain` (whether the crowd is a `membrane` you cannot see or walk through)
→ `drift` (whether the press CARRIES a body). The instructive part is that
`weather.py` in this same package hit this exact failure with a real measured
case — the Blizzard turn 2 note at `weather.py:103-120`, where a fully correct
declaration normalised to a calm spring day — and answered it with
`_SYNONYMS` plus a substring pass and a `None`-means-keep contract
(`weather._resolve`, `weather.py:173-199`). `crowds.normalize_band` has none of
that, and its docstring argues that falling to the smallest band is safe,
which is the same argument the weather default made before it was measured.

**F19. `place_purpose`'s light default admits an unreadable value.** Covered as
drift in F16; as a silent-unknown it is the second half: `light.get(…, "full")`
means any light level the three-entry map does not contain — including a
future darker rung — reads as full sight and echoes the room's affordances.
The conservative direction here is to withhold, and the default withholds
nothing.

**F20. `survival` drops a vital rather than reporting a bad one.**
`_clamp` returns `None` on a non-numeric value (`survival.py:110-114`), and
`tick_vitals` writes `{k: round(v, 4) for k, v in current.items() if v is not
None}` (`survival.py:258-259`) — so a vital that failed to parse is silently
removed from the record, and `vitals_of` then merges the defaults back in
(`survival.py:154-156`). A body whose `air` was written as `"low"` is restored
to `air: 1.0` on the next tick, breathing freely, with nothing raised.

### Comments describing behaviour the code no longer has

**F21. `survival.VITALS`'s comment describes a tuple the dict does not hold.**
`survival.py:69`: `# name -> (baseline per HOUR of simulation time, starts_at)`
above `VITALS = {"air": 1.0, "stamina": 1.0, "nourishment": 1.0, "injury": 0.0}`
(`survival.py:72-77`). Those are starting VALUES, not rates and not a pair; the
per-hour rates are a different dict (`_PER_HOUR`, `survival.py:79-89`) and
`starts_at` exists nowhere in the file. Two readers in a row will look for a
`starts_at` field.

**F22. `paradox`'s epicenter fallback does not do what its comment says.**
`paradox.py:379-381`: `# Fall back to wherever the player is` followed by
`epicenter = next(iter(positions.values()), None)` — the first value in
`scene.positions` in dict insertion order, which is whoever the Director
happened to write first. The paradox wound then opens, consumes rooms and
spawns a warden at an arbitrary body's room. The comment's second clause
("there's always a scene in progress when a commit runs") is also not enforced:
`positions` may be empty and `epicenter` may be `None`, in which case
`_apply_warden_stage` writes `positions[warden_id] = None`
(`paradox.py:343`) — a position naming no room, which `AGENTS.md:67` names as
"a category error that every spatial query answers as `unknown`".

**F23. `persist/commit_mapping.py:209` says the seeded draw is taken where it
is not.** "the stochastic rung is a seeded draw in `offscreen.stochastic_ticks`
(free, replayable), taken at commit_mapping". It is taken in
`offscreen.advance_epoch` (`offscreen.py:1013-1016`), a separate commit domain
run from `persist/commit.py`; `commit_mapping.py` does not call it and does not
import it. Flagged here because it is the comment a reader of this package's
tick machinery will find first.

**F24. `paradox`'s mode table promises a separation the dispatcher does not
make.** The module docstring (`paradox.py:24-46`) presents five modes as
alternatives, with `toll` described as its own mode ("cost localizes to
travelers physically inside the wound"). `_apply_stage_consequence`
(`paradox.py:354-357`) runs `_apply_toll` for `hazard` as well —
and `hazard` is `DEFAULT_MODE` (`paradox.py:66`) with
`DEFAULT_TOLL_IN_RADIUS = True` (`paradox.py:67`). So the recommended default
mode also silently decays travelers' memory confidence
(`UPDATE memories SET confidence=MAX(0.05, confidence-?)`, `paradox.py:321-325`)
— a durable, irreversible write to another subsystem's column, described in
the docstring as belonging to a mode the story did not choose. The live
database has one chat on this configuration (chat 20,
`{'mode': 'hazard', 'escalation_rate': 1, 'toll_in_radius': True}`).

**F25. `crowds.talk_view`'s "newest first" is oldest-first.**
`crowds.py:568` says "newest first"; `crowds.py:585` slices the tail of an
oldest-first list and appends in order, so the returned list is oldest-first
within the last `cap`. It is delivered to the Director as `talk`
(`agents/director_views.py:338`) and to every observer
(`agents/common.py:837`), where ordering is what says which rumour is current.

### Tests that assert by absence, or on source layout

**F26. Three of this slice's guarantees are enforced by grepping source
text.** All three pass today; all three are silently satisfiable.

- `tests/test_degradation.py:180-192` asserts the string `"lost_at"` does not
  appear in any `*.py` under nine named packages. `tools/`,
  `extension_runtime/`, `language_runtime/` and `browser_tests/` are not in
  the list, and renaming the function makes the assertion vacuous rather than
  failing.
- `tests/test_routines.py:142-151` reads `inspect.getsource(routines)` and
  asserts `"wset("`, `"INSERT INTO"` and `"chat_complete"` are absent. A write
  through `qi("INSERT OR REPLACE …")`, `qtx`, `q("UPDATE …")`, or any helper
  that wraps a write satisfies all three. The module docstring
  (`routines.py:184-189`) states this test as the structural guarantee — "which
  a test pins by reading this source" — so the doctrine is stronger than the
  check.
- `tests/test_living_world.py:395-407` asserts `"place_obligations"` and
  `"owed_history"` do not appear in six named `agents/*.py` files. The
  obligation ledger is reachable as `living_world.OBLIGATION_KEY` and through
  `attach_owed_history`, neither of which the grep names, and the six-file list
  is maintained by hand against a package that has grown `director_views.py`,
  `director_fanout.py`, `director_scopes.py`, `director_reconcile.py`,
  `director_movement.py`, `director_floors.py`, `director_evidence.py`,
  `composer.py` and `common.py` since it was written — every one of which
  assembles a payload. `AGENTS.md:51` cites this test as pinning that the
  ledger has one reader.

### What offscreen simulation and gap-filling are allowed to manufacture

Both paths MANUFACTURE events nobody witnessed, so this section is the one the
brief asked for specifically. The structural separation is real and mostly
holds: `agent_context` is an allowlist on a signature with no `scene`
parameter (`offscreen.py:1530`), `land_agent_tick` writes movement into the
subject's own trail and never `scene.positions` (`offscreen.py:1850-1860`),
consequences pass `mint_consequences` like every other fuse, and `gaps._skeleton`
attributes world events on a structured `entity_id` rather than a prose sweep
(`gaps.py:224-230`). Three things do not hold.

**F27. Every tick this package composes names the subject in the third person,
and the one reader delivers it to that subject.** The composers:
`_IDLE_TICKS` (`offscreen.py:337-341`, `"{who} goes about their own
business…"`), the intention branch (`offscreen.py:390`,
`f"{who} keeps quietly at it: …"`), `compose_tick` (`offscreen.py:1097-1108`)
and `compose_agent_tick` (`offscreen.py:1770-1777`) — all four lead with the
subject's display name. The reader is `gaps.interim_for` → `gap_for` →
`_skeleton`, which copies `tick.get("tick")` into `events[].summary`
(`gaps.py:311-312`), and `agents/character.py:3135-3149` hands the whole
record to that same character as `payload["while_you_were_offscreen"]`.
The identity floor applied there is `scrub_names_deep(_interim, _name_scrub)`
— `observer_name_scrub`, which gates OTHER people's names. It is not
`self_reference_forms` / `_composer_self_forms`, the floor that rewrites a
mind's own name and minted epithets into second person
(`agents/common.py:4086`, `agents/perception.py:3330`, applied at
`perception.py:3989` and `4225`). `Design.md:203` records "A mind is never told
about itself in the third person, by name OR by the label strangers use for it
— **Built**"; `AGENTS.md:43` says the floor "runs in the other direction too".
This payload is the exception. Nothing is delivered today because of F30, but
the moment the seeded rung writes a batch, every mind's own offscreen record
arrives written about them.

**F28. `background_claims.canon_entry` writes the claimant verbatim into canon
prose, and the live canon contains engine uids.** `background_claims.py:292`:
`claimant = str(rec.get("claimant") or "").strip() or "a bystander"`, spliced
into `'%s said: "%s" — the Director has established this as true.'`
(`background_claims.py:298`). No check that the claimant is a display name
rather than an id — the module that answers that question,
`world/subjects.py`, is not consulted. Measured on the live database, 2 of 7
ratified rows in `lore_entries`:

```
3524  other  a8becaa367e148be said: "Never heard of Lugunica..." — the Director has established this as true.
3526  other  635a740debcd433f said: ""Greens, fresh-picked today..."" — the Director has established this as true.
```

Three separate defects visible in those two rows: (a) an opaque engine
identifier is now a person's name in canon lore, and lore is the one payload
`AGENTS.md:43` names as passing the identity floor only for WHICH entries
arrive, never for who they may name — `search_lore` → mapping → every
perceiver's payload; (b) the claim text already carries its own quotation
marks and `canon_entry` adds a second pair; (c) the appended clause asserts a
DENIAL as established truth — "Never heard of Lugunica" is now canon, stamped
"the Director has established this as true". The module's "Attributed, never
paraphrased" argument (`background_claims.py:284-290`) is right about not
putting a second author in the chain, and it does not follow that the line can
be wrapped in an assertion of truth without reading what the line says.

**F29. Ratification is inferred from a substring, and 7 of 7 live claims
ratified.** `background_claims._verdicts:395-396` ratifies when the Director
names the claim explicitly OR when `any(r.casefold() in text_cf for r in refs
if len(r) >= 4)` — any four-character reference appearing anywhere in the
resolved event text. The resolved event summarises the beat, and the beat
contains the presence's line, so a proper noun the presence just said is
almost certain to appear in the Director's own prose. Measured: the live
`background_claims` blob (chat 67) holds 7 records, **all 7 `ratified`, 0
contradicted, 0 expired**, with 7 matching `lore_entries` rows. The design's
"three possible outcomes are all ordinary fiction"
(`background_claims.py:16-21`, `BACKGROUND_LIFE_DESIGN.md:983-992`) has
collapsed to one, and the one it collapsed to is the only irreversible branch:
`write_canon` is a one-way door.

**F30. Every offscreen tick stored in the live corpus is dropped as unproven.**
`gaps._skeleton:308-310` requires both `basis` and `disposition` on a tick or
it counts it `unproven` and drops it — correct, and the reason is well argued
(`gaps.py:270-281`). Measured across all 11 `offscreen_log` world rows: 17
batches, **all with `rung: None`**, carrying 18 events, **all with
`basis: None, disposition: None`**. So the entire delivery path from
`offscreen_log` to a mind's `while_you_were_offscreen` currently delivers
nothing, and every tick in production predates both the rung tag and the
provenance stamp. This is the honest state, not a defect — but it means F27
has never fired, `interim_for` has never returned a record from that ledger,
and any claim that this path is exercised is unsupported. Companion figures
from the same read: 13 `offscreen_epoch` rows with reasons
`{opening: 7, location: 4, (location, due_event): 1, baseline: 1}` — the
hour-bucket `time` trigger and `reactive_due` have never fired; `crowds`: 0
rows in the whole database; `offscreen_plans`: 0; `place_obligations`: 0.

### The rest

**F31. `crowds.talk_view(crowd, 0)` returns the entire ledger.**
`crowds.py:585`: `crowd_hearsay(crowd)[-max(0, int(cap)):]`. In Python `-0 == 0`,
so the slice is `[0:]` — asking for nothing returns everything. Verified by
execution. Neither live caller passes 0 (`agents/common.py:837` uses the
default 2, `agents/director_views.py:338` passes 4), so this is latent; it is
recorded because `cap=0` is the natural way to express "this observer
overhears nothing", and it would deliver the crowd's whole rumour ledger
instead.

**F32. `offscreen.PLAN_CAP` does three different jobs, and one of them can
evict an active plan the other two just approved.** `offscreen.py:134` defines
one constant, used as: ops accepted per beat (`offscreen.py:751`,
`raw_ops[:PLAN_CAP]`), the ACTIVE-plan ceiling (`offscreen.py:758`,
`len([p for p in plans if p.get("status") == "active"]) >= PLAN_CAP`), and the
stored-list truncation (`offscreen.py:786`, `wset(cid, PLAN_KEY,
plans[-PLAN_CAP:])`). The last one counts every plan including `cancelled` and
`completed` ones. With 7 active plans and 5 cancelled ones in the list, the
active check passes, an 8th plan opens, and the write keeps the last 8 of 13 —
silently discarding five records that may include active plans, with no
warning and no `ctx.add_warning`. `advance_reactive_plans` then finds fewer
plans than `apply_plan_ops` reported as `active`.

**F33. `paradox._force_restore_anchor` writes a decommissioned table and
bypasses the entity projection.** `paradox.py:427-437`. It `INSERT`s directly
into `world_entities` (`paradox.py:430-434`) — which `CLAUDE.md`,
`AGENTS.md:57` and `core/db.py:680-686` all describe as a DERIVED projection
of the scene commit, built only by `persist/commit_entities.commit_world_entities`
— minting a row the `world.scene` blob knows nothing about, with
`kind="person"` and the entity id as its name. And it `DELETE`s from
`world_placements` (`paradox.py:437`), which is decommissioned:
`tests/test_world_authority_consolidation.py:16` states there is "no runtime
writer or reader", and this is a runtime writer. The table still exists, so
the statement does not raise; it simply deletes from a table nothing reads.

**F34. `paradox.get_policy` will raise on a hand-edited config.**
`paradox.py:98`: `float(stored.get("escalation_rate", 1.0))` with no guard,
inside a function called from `_trigger_paradox`, `_advance_paradox` and the
GET route. Every sibling normaliser in this package falls back rather than
raising (`normalize_living_world`, `normalize_weather`, `importance_for`,
`normalize_band`); this one takes the whole commit domain down. Its neighbour
two lines up (`mode`) is guarded.

**F35. Two `weather.py` constants are used above their definition.**
`_UNLIT_PRECIPITATION` is read at `weather.py:272` and defined at
`weather.py:525`; `_DEEP_WORDS` is read at `weather.py:302` and defined at
`weather.py:351`. Legal at call time and fine today; it is the one place in
this otherwise carefully ordered file where moving a function above its
neighbour would produce a `NameError` at runtime rather than at import.

**F36. `comfort._warm` can match across a field boundary.**
`comfort.py:112-116` zips adjacent tokens looking for a qualifier followed by
a medium, and `comfort.py:240-242` builds the token list by concatenating
`other`, `eid`, `kind`, `name` and `description`. A record whose `name` ends
"…warm" and whose `description` begins "Pool of…" reads as warm water. Cheap
to fix by tokenising per field; recorded because the module's whole argument
(`comfort.py:75-78`) is that a qualifier must be ADJACENT to its medium, and
adjacency across a join is not adjacency in a sentence.

---

## Unverified suspicions

Recorded separately because I could not close them.

- **`background_claims.CLAIM_TTL_TURNS` may never have expired anything.**
  Zero expirations in the live blob (F29), but with 7/7 ratified there was
  never an opportunity, so this is `no chances` rather than 0%. It cannot be
  distinguished from "expiry works and nothing reached it" without a corpus
  that produces an unratified claim.
- **`crowds.crowd_uid`'s `int(chat_id)` / `int(since_turn)`
  (`crowds.py:191-194`) will raise `TypeError` on a `None`.** Every live
  caller passes integers, and `apply_ops` is the only production path, so I
  could not construct a reachable failure — but `new_crowd` is a public
  function of a module documented as pure and total.
- **`_verdicts`' four-character reference floor (`background_claims.py:396`)
  looks tunable, but "Greens" and "Capital" are already in live canon as
  ratification keys.** Whether a shorter or longer floor would have changed
  any of the 7 outcomes is not derivable from the stored record, which keeps
  refs but not the resolved text they matched against.
- **`advance_weather` re-rolls from the CURRENT sky on every beat inside one
  drift window, not once per window** (`weather.py:656-698`, called from
  `persist/commit_scene_state.py:587` with the total elapsed clock). I
  expected a sky that walked several rungs inside one hour; executing five
  chained beats across four seeds showed it reaching a fixed point on the
  first step every time, so the documented "roughly one step per in-story
  hour" holds in practice. Recorded because the property is accidental — it
  depends on `_SKY_NEXT` rows leading with their own key — and nothing tests
  it.
- **`gaps._skeleton`'s legacy `scheduled_events` fallback appends entries with
  `turn=None`** (`gaps.py:268`, `append_if_owned(row)` with no `turn`
  argument, against `gaps.py:250` which passes one). Nothing downstream
  appears to read `events[].turn`, so I could not show a consequence.

---

## What the code actually does, module by module

Written from the code, then checked against `Design.md`, `AGENTS.md`,
`docs/guides/`, `docs/design/BACKGROUND_LIFE_DESIGN.md` and
`docs/design/OFFSCREEN_WORLD_COMPLETION.md`. "Docs right" entries are recorded
deliberately — they are what makes the exceptions credible.

### `degradation.py`

What a claim loses per retelling: three tiers (count → place → name, name
last so a rumour stays useful near its source), a hop-count exhaustion bound,
and a `lost_at` diagnostic deliberately never shown to a model. Pure — strings
in, strings out, derived at read rather than stored, so re-degrading cannot
compound. `_replace_phrases` is longest-first and swallows the leading
article, and `_PLURAL_NUMBER_WORDS` excludes `one`/`a` so subtraction cannot
claim more people than the witnessed surface said.

Docs checked: `OFFSCREEN_WORLD_COMPLETION.md:110-113` describes it exactly
("count, then place, then name, with the name last"). `AGENTS.md:49`'s
degradation-at-mouths doctrine matches — nothing here degrades on a read.
Right. (F26 is about its test, not its code.)

### `routines.py`

Approach A's floor: occupancy bands on an eight-watch day curve with
place-seeded phase jitter and per-day amplitude jitter, entropy facts gated on
what the room's own name affords, and `residue_for` — the capped
(`RESIDUE_CAP = 3`) present-tense diff delivered at re-entry, with fired
consequence fuses ranked first as layer-1 fact and plausible motion after.
Reads three ledgers (`gaps.LAST_SEEN_KEY`, `living_world.fired_consequences_at`,
`place_purpose.assumed_affords`) and writes nothing.

Docs checked: `AGENTS.md:51` ("`world/routines.py` (pure; writes nothing)")
matches. `Design.md:259` ("A recomputes routine/entropy/occupancy at contact")
matches. The one consumer is `agents/director.destination_residue`, and the
Director is entitled — verified: no character payload reads it. Right.
(F14; F26 for its test.)

### `comfort.py`

Ambient comfort as a pleasure-level FLOOR for `resolve_hedonic`: a closed
soft/warm token vocabulary graded by evidence tier (contact > station-at >
station-near), bodies excluded from being furniture via the `attire`/`scales`/
`vitals` probe, and `rest_affording` as the narrow lying-on-a-soft-support
fact `survival.tick_vitals` spends as passive stamina recovery. Reads only
structural scene state; the `_posture_of` fallback also reads the legacy
`state.position` spelling, which the in-file comment cites a live record for.

Docs checked: `Design.md:171` (bounded pain/pleasure) is consistent; the
module's own seam note (`comfort.py:30-37`) about place purpose taking up
`rest_affording` is accurate — `place_purpose.witness_affords:324` is the
taker. Right. (F13, F36.)

### `survival.py`

Four 0..1 vitals on the simulation clock, absent-means-off, with air as a
countdown that only runs while sealed in a closed parented interior
(`is_sealed_in`, which correctly treats a transparent or barred enclosure as
airtight). Seeding is idempotent and never resets an existing record;
`vitals_facts` is silent for an ordinary body so the common case costs nothing.

Docs checked: no guide row states the vitals ladder; the module's own
contract is internally consistent, and `AGENTS.md:63`'s awareness machinery is
a separate axis that does not read these. `place_purpose` reads
`vitals_of`/the 0.4 tier correctly. (F6, F20, F21.)

### `mechanics.py`

The ordered deterministic sweep: fire due `transit_arrival`/`news_arrival`/
`consequence` rows for THIS frame, schedule new arrivals from
`entity.state.transit`, expire due conditions, recompute dock edges when an
arrival fired, run vehicle-zone/companion-carry inference. Database-pure —
every durable effect is an `event_op` for `commit_transit_sweep` to apply
inside the turn transaction. The consequence branch's base-revision check
(`mechanics.py:141-148`) cancels a fuse minted from a turn the story no longer
contains, and the notice is emitted only when the player stands at the fuse's
location.

Docs checked: `AGENTS.md:61` and `docs/guides/PIPELINE.md`'s commit ordering
("transit sweep — first, because it mutates the prepared scene") match.
`living_world.py:23-29`'s epistemic contract — "The firing writes no notice
unless the player is standing at its location when it fires" — matches
`mechanics.py:151-158` exactly. Right. (F3.)

### `weather.py`

One sky per scene, exposure per room. A five-enum vocabulary with a synonym
table and a substring pass earned from a measured live failure; a
declared-over-standing merge so an unreadable word keeps what was blowing;
authored `exposure` with a keyword fallback that defaults to `enclosed`;
`weather_depth`'s layer-counting BFS (free hops through ambient barriers,
one layer per muffling boundary) with a deliberate unmapped-room assumption
and a deep-word override; per-channel `weather_words`; a seeded idempotent
drift; and the ground ladder (accumulate while landing, drain when not, three
beats per rung).

Docs checked: `AGENTS.md:62` is right in every particular it states — one sky,
exposure decides how much, `weather_words` takes a CHANNEL, exposure falls
back to a keyword pass and defaults to `enclosed`, drift is seeded and
idempotent, a declaration is written OVER the standing sky, extend `_SYNONYMS`
rather than widening an enum. It does not mention `thundersnow`, `has_lightning`
or the ground ladder, all of which are live. Right. (F2, F4, F9, F35.)

### `crowds.py`

A crowd as one row that costs the same whatever it holds: a four-rung band
(never an integer), density DERIVED from band against room, terrain in the
barrier vocabulary spatial already folds words into, `drift` as an OFFER the
Director resolves, band-preserving splitting with no conservation arithmetic,
one-way emergence refused for named cast and for anyone who has spoken, and
`uid`-keyed identity from birth. Also the anonymous carrier: a capped hearsay
ledger, `crowd_voice` attribution that is never a name, and `talk_view` as the
observer surface.

Docs checked: `OFFSCREEN_WORLD_COMPLETION.md:72` tags item 2 **BUILT** —
see the tag corrections below; it is half built. `Design.md` has no crowd row.
`agents/common.crowds_for_room`'s own-room scoping is real and matches the
module's claim. (F5, F15, F18, F25, F31; live corpus: 0 crowds ever.)

### `paradox.py`

Fixed points as declared existence predicates over `world_entities`, per-frame
independent paradox slots, a severity scalar climbing on the frame's own
simulation clock with a ceiling that force-restores the anchor, and five
consequence modes (`dread` inert, `hazard` room consumption via a distinctive
`room.notes` marker, `toll` memory-confidence decay for travelers in the wound,
`warden`/`bureau` an ordinary hunting scene entity). Spatial frames are
exempted so ordinary distance authoring cannot trip grandfather-paradox
machinery.

Docs checked: `Design.md:591-593` lists the subsystem and claims no more than
it does. The module's own comment at `paradox.py:76-86` — that the
room-consumption half was invisible until it was routed through `room.notes` —
matches `_HAZARD_WOUND_NOTE`'s use and `_restore_consumed`'s exact-suffix
strip. The mode table does not match the dispatcher (F24). (F7, F8, F22, F33,
F34.)

### `background_claims.py`

Lore a background presence invents, recorded as CLAIMED: a novel-proper-noun
detector with stopwords, titles, hyphenated names and a sentence-start guard;
content-hashed idempotent minting with an 8-turn TTL; a capped surface onto
every `director_resolve` payload; embeddings prepared before the write lock;
and settlement that WRITES ratified claims into the chat's own canon lorebook
rather than flipping a status field.

Docs checked: `AGENTS.md:47` is right about the central lesson (ratifying is a
write), about explicit-only contradiction, about both-lists settling as
contradicted and writing nothing, and about embeddings being prepared before
the transaction — all verified in `settle_claims`/`prepare_canon`. It is wrong
about the measurement (see corrections). `BACKGROUND_LIFE_DESIGN.md:955-1085`
describes the same design accurately, with the same stale figure. (F28, F29.)

### `subjects.py`

One spelling in, one id out, or the reason there is none. Per-kind resolution
through the durable ledger that already owns beings of that kind — cast row,
scene room then `room_registry` (live before retired), lore `entry_uid` for
factions and ungenerated places, scene entity for crowds — with an OPEN kind
vocabulary falling back to scene entities. Ambiguity resolves to nothing, with
the ambiguity in the reason; a name-keyed background presence gets its own
precise dead-end message. Nothing is ever minted.

Docs checked: `AGENTS.md:67`'s "one being, one name" is about the spatial fold
and correctly does not claim this module does it. The `faction` lore category
this depends on is real (`mind/memory.py:21-23`). `mint_consequences` and
`_normalize_plan_stages` both use it as the "quiet office" gate, as documented.
Right — the cleanest module in the slice.

### `place_purpose.py`

Three bases for what a place is FOR: `witnessed` (own vitals rising across two
consecutive same-room commits, or own body verifiably lying on a soft
support), `told` (a read-model of a stated-fact place belief, re-asked from
`belief_credence` on every commit touch and DROPPED when the belief no longer
survives), and `assumed` (derived read-side from the character's own
place-graph node names, never stored). Plus the live `here_affords` perception
echo, `felt_needs` at the 0.4 vital tier, and `place_options` ranked by basis
then by distance over WALKED doorways only.

Docs checked: `Design.md:180` matches the mechanism, with two naming errors
(see corrections). `AGENTS.md` has no row for this module. The design's
firewall argument — the lexicon is consulted only for a node the character's
own feet or eyes earned — is structurally true: `assumed_affords` takes a node
NAME and every caller passes one off `state.place_graph`. Right on the
substance. (F11, F12, F16, F19.)

### `gaps.py`

What changed about one subject between two turns, as a RECORD rather than
prose. Every ask goes through `subjects.resolve_subject` so a display name
becomes an id; stored prose rooms are dropped on read as well as write;
world events are attributed on a structured `entity_id` (never a payload prose
sweep) and windowed by the clock the last-seen ledger anchors; offscreen ticks
are owned by structured subject id or exact legacy actor, and then must carry
`basis` AND `disposition` or they are dropped as somebody else's omniscient
prose. `last_seen_update` records co-presence keyed by subject id, folding an
ambiguous spelling to nothing, and stamps the room itself so a room subject
has a clock anchor.

Docs checked: `OFFSCREEN_WORLD_COMPLETION.md:254` describes it as
`offscreen_log`'s one reader — half right (see corrections).
`AGENTS.md:48-50` correctly places the ladder's authority in `story/scene.py`
and does not claim this module's medium rung runs. `Design.md:252` says "The
low tier is built as specified", which is exactly right and quietly implies
the medium one is not — though nothing says it is unreachable. (F1, F1a, F17,
F27, F30.)

### `offscreen.py`

The largest module in the slice, and four things at once.

1. **The spend function** — importance (derived from cast membership, sheet,
   tier, authored psychology, memory rows, plus a card override that falls to
   the derived value rather than the floor) × distance (non-wall BFS hop
   buckets, pulled one step closer by an intention aimed at the player's room)
   → `inert | low | medium`, recomputed per tick, never stored.
2. **The free seeded rung** — `stochastic_ticks`, a real `random.Random(seed)`
   draw against the standing-intentions ledger, with fixed per-actor RNG
   consumption and an OWNERSHIP gate (`_intention_owned_by`) rather than the
   mention gate that put another mind's aim in a subject's tick.
3. **The epoch and the reactive rung** — `epoch_reasons` (opening, top-level
   location change, crossed hour bucket, due event, crossed plan deadline) as
   one stable frame-scoped opportunity per beat; `apply_plan_ops`, which
   accepts a Director plan op only when its `basis` is grounded in what the
   named character actually declared this beat (`_basis_is_grounded`, a
   substring-or-word-overlap check over that character's own returned text);
   `advance_reactive_plans`, which fires only the already-adjudicated effect
   with no deliberation and no model call.
4. **The paid rungs** — the profile tick (one bounded out-of-band call
   emitting `{doing, at, manner}` with word bounds, never a sentence) and the
   full `character_agent` rung (fail-closed `agent_context`, one character
   call proposing a word-bounded attempt, one Director call adjudicating it
   against the objective scene, one atomic landing guarded by epoch, base turn
   and the subject's own `last_epoch_id`).

The firewall reasoning is genuinely structural in the places that matter:
`agent_context` has no `scene` parameter, the allowlist is re-applied on the
way out, movement lands in the subject's own trail rather than
`scene.positions`, and the producer threads pin `active_frame_id` because a
fresh thread context would otherwise land frame-scoped writes in the present
frame.

Docs checked: `AGENTS.md:48` and `:50` match the code (rungs are
`schemas.BehaviorController`'s, a ceiling never an instruction, `reactive`
deliberately narrow, three composing gates for the paid rung, importance may
rank spend but never auto-opt-in). `Design.md:252` matches end to end.
`OFFSCREEN_WORLD_COMPLETION.md:202-300` matches every safeguard it claims to
have checked against source, except the one-reader line. (F1a, F10, F27, F30,
F32.)

### `living_world.py`

The shared five-approach ladder (A–E × off/floor/ceiling), the declared/built
split kept beside it in `LIVING_WORLD_BUILT` so an unbuilt tier cannot read as
built, `LIVING_WORLD_REQUIRES` mapping each depth onto the offscreen-life rung
it spends at, and `effective_depth`'s two clamps — lowered to the highest
BUILT depth at or below the request, and again to what the story's offscreen
ceiling permits, with the request preserved so landing a ceiling later is
opt-in. Plus approach B's fuse mint (`mint_consequences`: cap 2 per turn,
due clamped rather than refused, location gated through `resolve_subject`,
`disposition: resolved_fact` stamped) and approach D's obligation ledger
(recorded UNGATED because truth accumulates and settings gate surfaces, capped
at 12 stored and 4 honoured, surfaced only through `attach_owed_history` at
generation).

Docs checked: `AGENTS.md:51` names `LIVING_WORLD_BUILT` as the
declared/built authority and lists the right owners — verified. Its verbatim
phase-2 constraints hold in the code: information travels by carriers not
timers (there is no broadcast writer here), nothing privileges the player (a
fuse payload has no importance, priority or reputation field), everything
defaults off (`LIVING_WORLD_DEFAULT = "off"`), a fired fuse emits a notice only
at the player's location (enforced in `mechanics`, not here — correctly).
`Design.md:259`'s status line matches `LIVING_WORLD_BUILT` exactly. Right —
the best-documented module in the slice.

---

## Status-tag corrections

`docs/design/OFFSCREEN_WORLD_COMPLETION.md` carries per-item built/unbuilt
tags, which `CLAUDE.md` names as one of five competing status lists. Every tag
checked against source:

| Item | Tag | Verdict |
|---|---|---|
| §2 Crowds and persistent fixtures | **BUILT** (2026-08-10) | **WRONG — half built.** |
| §3 Information-carrier network | **BUILT** | Correct (outside this slice; `degradation.py` and `crowds.py`'s carrier half both present as described). |
| §4 Durable social history | **PARTLY BUILT** | Correct (outside this slice). |
| §5 Full `character_agent` rung | **BUILT** | Correct in substance; one supporting claim is wrong. |
| §7 Rumor-ledger ceiling | **BUILT** | Correct (outside this slice). |
| §7 Antagonist-ladder ceiling | **BUILT** | Correct — `offscreen.schedule_agent_ticks` is whole. |
| §1, §6, §8 | untagged / open | Correct. |

**§2 is tagged BUILT and its own body lists five required steps, of which two
are absent.** `OFFSCREEN_WORLD_COMPLETION.md:98` requires "persistent location
fixtures", described at `:88-92` as one of "two related forms" the item needs —
"barkeeps, vendors, guards, attendants, and regulars" belonging to a location
and re-meetable. Verified: no fixture representation exists in `world/`,
`story/scene.py`, `llm/schemas.py`, `persist/commit.py` or `agents/common.py`;
the only occurrences of the word in the tree are `spatial_containment.py:13`'s
entity-kind list and prose in `spatial_frames.py`/`spatial_geometry.py` about
poses relative to room anchors. Step 3 also requires "adjudicated drift **and
separation**" (`:102-103`); `crowds.py` has `drift` and has no separation
concept. The item's own closing paragraph — "The module shipped pure and
correct and could not occur… Worth remembering when reading any other 'built'
line in this document" — is exactly the warning this row now needs applied to
itself.

**§5's supporting claim at `:254` is wrong.** "`offscreen_log` has exactly one
reader, `gaps.interim_for`". It has three: `gaps._skeleton` (`gaps.py:287`,
reached by `interim_for` AND by `offscreen.profile_summary_record` →
`gap_for`), and `world/spatial_frames.py:906` and `:1053`, which read and write
it across frame fork and merge. The safeguard the sentence supports — that no
diagnostic surface exists to gate — is unaffected; the count is not.

### Other status claims that no longer match source

- **"0 claims in production" is stale in three places.** `AGENTS.md:47` ("this
  lane has produced 0 claims in production, so there is nothing measured to
  tune"), `world/background_claims.py:64` ("the mechanism has produced 0 claims
  across the whole production corpus"), and
  `docs/design/BACKGROUND_LIFE_DESIGN.md:1070` ("produced **0 claims** (2,411
  `background_react` variants…)"). The live database has 7 claims and 7
  matching canon `lore_entries` rows (chat 67, turns 10-23). There is now a
  measurement, and it says something (F29).
- **`Design.md:180` names two functions that do not exist.**
  "`memory.recalled_places` surfaces at most two walked-route options" —
  `recalled_places` is a payload KEY built in `agents/character.py:2999`;
  `mind/memory.py` contains the string zero times. The same phantom appears in
  `agents/character.py:3015`'s own comment. The row also says "live
  `perception.here_affords` echo"; `here_affords` lives in
  `world/place_purpose.py` and is called from `agents/character.py`, never
  from `agents/perception.py` — `perception` is the payload SECTION it lands
  in, which reads as a module attribution.
- **`AGENTS.md:51`'s claim that the obligation ledger has one reader pinned by
  a test** is true of the code and weak in the test — see F26.
