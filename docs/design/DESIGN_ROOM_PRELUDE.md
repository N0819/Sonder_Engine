# The Writers' Room designs the ground, and asks first

Status: BUILT 2026-09-17 (this note and the code landed together; the
conformance row is in `Design.md`, the residuals in § 7). It continues
[`DESIGN_OPENING_PLAN.md`](DESIGN_OPENING_PLAN.md), which put the Room in
front of the first beat; this note puts it in front of the GROUND that beat
stands on, and gives the player one place to say what they want before either
runs.

## 1. The defect

**An inhabited location was designed by one `utility` call, and the Writers'
Room was told about it afterwards.**

`charter_generate.propose_town` sent `_PLAN_SYSTEM` -- 2,800 words beginning
"You design one inhabited location from supplied lore" -- to the `utility`
role and asked for the whole object back at once: the map, every institution,
its posts and upkeeps and populations and economy, a naming law and a look
law. Both launches reached it the same way. A greeting quick start ran
`generate_lived_location` from the sentence the player typed into the
lived-location control, and only then ran `run_opening_plan`, which planned
the opening's rooms around a town that was already planted; a scenario chat
posted the same request one HTTP call earlier, to `POST
/api/chats/{cid}/charters/generate`, before anything had read the scenario.

Owner, 2026-09-17, in two sentences that are the whole of this note's
argument:

> Kill whatever is sending this prompt and replace it's routing with the
> writers room entirely in the quick starts as this is work that belongs to
> the writers room not utility.

> The writers room is meant to design charter locations and maps. The prompt
> I just mentioned is also wildly inefficient in comparison to the writers
> room multi tool call planing and execution.

Both halves are visible in what the one-shot kept doing. It had exactly one
attempt and no way to be told it was wrong: a plan that did not close failed
the launch twenty seconds later, and a model that ignored `reasoning_effort:
off` spent 99% of a 16,000-token budget on a trace and returned JSON cut off
inside a washroom (chat 136, 2026-09-16 -- the retry-with-more-room in
`_json_call` is the scar). It was handed a slice of lore it could not ask a
question about, and it could not see the story's own rooms, its cast, or the
passage the story opens on.

**And neither launch asked the player anything.** They pick a persona, a
greeting, a lorebook and a horizon, press start, and the next thing that
happens is a story. There is no moment at which "I want this one to be about
the boat, not the town" is a thing you can say -- and it is the cheapest
possible moment to say it, because nothing has been built yet.

## 2. What runs now

A third state between "created" and "running": **the Room has the floor.**

```text
greeting quick start, prelude:
    seed chat/cast/language/lorebook -> record the launch -> Room asks -> STOP
    [player answers in the room panel, or not]
    begin -> ground brief -> generate_lived_location -> minds -> opening plan -> turn 0

scenario chat, prelude:
    POST /api/chats -> persona -> cast -> record the launch -> Room asks -> STOP
    [player answers in the room panel, or not]
    begin -> ground brief -> generate_lived_location
    [first beat when the player writes one, as a scenario chat always has]
```

Without the prelude both launches run exactly as before, with ONE change:
the brief the location generator is handed is written by the Room
(§ 4), and the opening plan reads whatever the player said (§ 5).

Three passes of the Story Planner now run before a story has turns, each its
own regime, none of them able to publish anything:

| Regime | When | Product | Budget |
|---|---|---|---|
| `prelude` | the player asked to talk first | one question, into the room thread | 6 steps / 120s |
| `ground` | a lived-in location was asked for | the BRIEF, as its reply | 10 steps / 180s |
| `opening` | both launches, as before | one package: rooms, placements, a note | 24 steps / 360s |

`prelude` and `ground` mint no mandate at all, because neither writes: the
read tools need no grant, and `spend_limits` returns its default 60 calls per
reply with no active grant. The opening's engine-minted mandate is unchanged.

## 3. The pause

`story/prelude.py` holds it.

**A launch that takes the prelude is recorded whole.** `record_setup` keeps
the arguments the launch screen sent on the chat (`story_setup`), and
`begin_story` runs from that row. The browser could have re-sent them, and
then a story's ground would depend on a form still being open in a tab; more
practically, the failed-setup path (2026-09-08) picks a broken launch up from
the chat, and a prelude that only existed in a tab would have nothing for it
to pick up.

**The cut is between the story's identity and its ground.** Everything above
it -- who is in the story, what language it is in, which book it draws on --
was settled by the launch screen and is seeded immediately; everything below
it is the place, which is what the prelude exists to let the player have a
say in. `tests/test_room_prelude.py` pins the cut by reading
`start_story`'s own source, because it is a claim about an ORDER and the
function is long enough for a later edit to move a stage across it without
anybody noticing.

**Begin resumes rather than re-runs.** `start_story`'s resume path
(2026-09-08) already asks the CHAT whether each stage's work is there, so
`begin_story` calls it with `resume_chat_id` and the seeding above the cut is
not repeated. Nothing new was needed for that, which is the reason the cut is
where it is.

**`awaiting_begin` is the turn, not the row.** A setup left behind by a
launch that went on to write turn 0 anyway would otherwise hold a running
story at the door for good, with the composer hidden behind a button that has
nothing to do.

**A prelude is not a failed setup.** It clears `QUICK_START_FAILURE_KEY` on
the way out, so the library shows a story waiting rather than a story broken.

**The new world rows need no archive work and no id remapping.** The archive
exports every world key but a denylist (`chat_archive.
UNEXPORTED_WORLD_KEYS`), so `story_setup`, `prelude`, `location_plan` and the
short-lived `location_draft` are carried by construction. `story_setup` does hold `char_id`, `persona_id` and
`lorebook_id`, which a branch or clone would normally have to remap -- and
does not have to here, because branching requires a turn to branch FROM and
`begin` clears the row before the first one exists. A story that carries a
live setup is a story with no turns, which is a story nothing can branch.

## 4. The Room designs the location

`story/location_design.py` holds the draft; `story_planner.run_location_plan`
runs the pass; `charter_generate.propose_town`'s existing `model_call` seam is
where it lands, threaded through `generate_lived_location(...,
town_planner=)`.

**The plan is drafted, not demanded.** Four tools, open only while a pass is
running:

| Tool | What it does |
|---|---|
| `draft_location` | name, structure grammar, and rooms -- rooms MERGE across calls, so the map goes down a handful at a time |
| `draft_charter` | ONE institution per call, replacing any already under that key; `remove` drops one |
| `review_location` | closes the plan as drafted and returns what the closure refused |
| `submit_location` | declares it finished, refused unless the review passes at the current contents |

The Room reads the lore with `search_lore`/`read_lore`/`scan_lore` -- which is
the efficiency the owner named: the one-shot was handed a slice it could not
ask about. The task carries the selected slice, says when it was truncated,
and carries `author_brief`, `player_said` (§ 5) and the launch's constraints.

**The review is the real closure, not a shape test.** `review_location` runs
`charter_generate.close_plan` against the draft and reports its exception. A
cheaper test written beside it would be a second opinion about what the
closure accepts, and the drift would surface as a launch that failed after the
Room had been told its plan was good. Drafting anything clears the last
review, so a plan edited after its check is checked again before it can be
submitted.

**The reservation is derived from the draft.** Without an authored naming law
the story's identity reservation depends on the PLAN's own naming laws
(`_plan_naming_laws`), which do not exist before the plan does -- so the
checker derives it from what is drafted, by the same two lines the launch
uses on the finished plan. A reservation computed before the pass would have
been a different one, and a review that passed under it could still lose a
resident's name at the launch.

**One statement of what a plan is.** `charter_generate.plan_specification()`
returns `_PLAN_SYSTEM` itself, and the Room is handed it as `shape`. Two
copies of a 2,800-word specification would drift, and the drift would be a
plan the Room wrote correctly and the closure refused.

**Only the PROPOSAL moved.** `close_plan`, `_remap_generated_town`,
`plant_structure`, the registry save, the presimulation, the history and the
job's resume/salvage/lock are untouched, and so is the artifact's shape --
the pass returns exactly what `propose_town` returned. That is also why the
Room does not publish a `request_location` package instead: a package
validates BEFORE its long operations prepare, so rooms joined to a town the
same package plants cannot validate (the class chat 131 hit), and a planner
budget must not be able to strand a half-planted town.

**A pass that submits nothing FAILS the generation.** There is no fallback to
the one-shot, deliberately: falling back would keep alive the thing this
replaces. The launch already has the failure path for it -- the story stays
in the library, marked, with its retry (2026-09-08) -- and the `location_plan`
row says what the Room had drafted when it stopped, so the author can decide
whether to ask for less.

## 4b. The prehistory is the same pass's work

`propose_history` was the second one-shot `utility` call in the family, and on
the second live run it is what failed the launch (§ 4a). The Room drafts it
now, in the same pass, through `draft_history`: `eras` for what those months
were, and two to eight physical `interventions` the simulator runs through
them -- the same closed vocabulary `_HISTORY_SYSTEM` stated, physical
circumstances only, the simulator deciding what came of them.

Two things fall out of drafting it there rather than after.

**The review becomes exact.** `close_plan` takes the history, so the review
that § 4 called "the real closure" was in fact closing a slightly different
question from the launch — `history={}` against the launch's real one. That
gap is gone: the draft holds the history, and `review_location` closes with
it. A launch whose closure asked for months and got none is also a review
error now, not a surprise at the end.

**One return value carries both.** `propose_town`'s contract is that it
returns a plan, so the prehistory rides back under `PREHISTORY_KEY` and
`charter_runtime._plan_lived_location` lifts it off before anything — itself,
`close_plan`, `_plan_naming_laws` — sees the object. One string, two
modules, held together by a test. The alternative was a second round trip to
the planner for a value it had already written.

`propose_history` stays as the fallback for every caller that passes no
planner, exactly as `propose_town` does.

## 4c. A resume pays for nothing twice

A location design is the most expensive thing a launch does -- 227 to 250
seconds and six to nine model calls, measured across chats 149 and 150 -- and
every stage after it can raise. Owner, chat 150:

> you've made it so i have to rerun every single step instead of recovering
> from what the writers room sucesfully planned, make sure that the resume is
> runnable from every step in this possible story setup.

`start_story`'s resume rule (2026-09-08) is that every stage asks the CHAT
whether its own work is already there, rather than trusting a recorded stage
name. Three stages were not asking. They are now, and
`tests/test_room_prelude.py` pins the whole list in one place because it is a
claim about a long function a later edit can quietly break.

| Stage | What it asks |
|---|---|
| language, persona, fiction model, clock | overwritten; idempotent |
| cast row, lorebook attach | `INSERT OR IGNORE` |
| the town | `registry_rows(cid)` -- the rows are the fact, a marker is a claim about them |
| **the location DESIGN** | `location_design.submitted_for(cid, digest)` -- **new** |
| minds | upserted on `(chat, character, event_key)` |
| **the journey history** | its own `handoff.complete` -- **new** |
| **the opening plan** | `opening_plan_record(cid)["published"]` -- **new** |
| turn 0 | the existing row is reused |

**The design is held against the request it answers.** A submitted plan is
kept under `location_design.SUBMITTED_KEY` with a digest over the fields that
decide what the place IS -- the brief, the lore, the scale, the topology, the
required rooms, the featured residents, the population, the naming register.
A retry of the same ask adopts it whole and makes no model call; a retry with
a changed brief is a different question and designs again. It is forgotten
the moment the town is planted, because after that the registry is the fact
and a kept copy would be offered to the next pass as work in progress -- and
would plant a second town beside the first.

**A published opening plan is skipped; a plan that published NOTHING is not.**
The row exists either way, so skipping on its mere presence would make a
stalled opening permanent. That is the failure a retry exists to have another
go at.

## 4a. What the first live run found (2026-09-17)

One greeting quick start, chat 149, the first time any of this ran against a
real launch. It found one defect, and it is this note's own:

**The planner was handed the wrong argument, and nothing short of running it
could have said so.** `room_town_planner(cid)` returned a callable taking a
PAYLOAD; `_plan_lived_location` called it with `closure_inputs` to obtain the
model call. So the Room ran with the closure as its payload -- no
`author_brief`, no lore, no constraints -- designed fourteen rooms and two
institutions out of nothing over 249 seconds and eight calls, submitted them,
and handed back a plan that `propose_town` then tried to CALL: `TypeError:
'dict' object is not callable`. The launch failed, the story was kept and
marked as the failed-setup path intends, and 249 seconds of authoring was
thrown away. Two curried arguments of different meanings is what made the
mistake available; the contract is now `(payload, closure) -> plan`, both at
the call.

The test that was supposed to cover this checked that the SOURCE contained
`room_town_planner` and `town_planner=`. It did. Every name in the broken
wiring was spelled correctly, which is the whole lesson: the seam is now
exercised (`test_the_planner_is_handed_the_towns_payload_and_its_plan_is_used`),
and reverting either half of the fix reproduces the exact `TypeError`.

**What the run did say about the budget**, with the caveat that the pass had
nothing to read: eight calls, six steps, 249.5 seconds, submitted -- against
40 steps and 900 seconds. Response tokens per call ranged from 320 to 10,708,
and the two calls that drafted the map and the institutions were 93s and
101s.

**The second run, same chat, with the payload fixed:** six calls, five steps,
240.5 seconds, fourteen rooms and two institutions again -- this time from a
real brief and real lore. So a pass with something to read cost no more than
one without, and the 40-step ceiling is not close to binding. That run then
died one stage later, in `propose_history`: the `utility` role's router
served a thinking-only model, which refused `reasoning_effort='none'` with
HTTP 400, after which four calls spent the whole 4,000-token budget on
reasoning traces and returned no content at all -- 104 seconds, no answer,
and the Room's 240 seconds of design thrown away with it. That is § 4b's
reason for existing, and it is the same complaint the owner made about the
town prompt, arriving on its sibling.

**The third run, chat 150, found the rest of it.** Twenty rooms, three
institutions, nine calls, five steps, 227.4 seconds -- and then the launch
died two stages later in `compile_journey_history`, four calls each spending
a 6,200-token budget on a reasoning trace and returning nothing. Two things
came out of that run, and they are § 4c and the paragraph below.

**Every cap in this family was a guess from 2026-09.** Owner: *"The cap is
stupid is my determination I've turned of reasoning"*. The generation calls
carried four hand-picked ceilings -- 16,000 for a plan, 4,000 for a
prehistory, 4,000 for the historian's narration, `2000 + 600 * count` for a
journey -- while a reasoning model bills its thinking against the same
budget. The owner's own 2026-09-04 ruling had already answered this once, for
the Room (`story.room_calls.room_max_tokens`: every response cap is the same
number, the host's, so no single call is the one that truncates); it was
never applied here. `charter_generate.plan_max_tokens()` is that ruling, in
this family. `providers._clamp_max_tokens` only ever lowers, so a host that
sets 8,000 still gets 8,000, and `PLAN_MAX_TOKENS` survives as the fallback
for a host that cannot be read.

**What it costs and what it buys.** The budget is 40 steps / 900 seconds, the
largest of the four launch regimes, against a one-shot that had one attempt
and a 16,000-token ceiling it regularly spent on a reasoning trace. Per call
the work is far smaller -- a few rooms, or one institution -- so the ceiling
is a ceiling on ITERATIONS rather than on how much has to come back correct
at once. Unmeasured live as of this note; § 7.

## 5. What the player said

`prelude.player_wants` returns the player's own lines from the room thread,
cut at the moment they pressed begin.

Both later passes read it: the `location` task carries it as `player_said`
beside `author_brief`, and so does the `opening` task. The opening reads it
through `_opening_task` rather than through a parameter, deliberately -- the
two launches reach the opening plan by different routes (the greeting quick
start calls it; a scenario chat gets there through `web.app._plan_opening` on
turn 0), and a parameter would have had to be threaded through both and
remembered by the next one. The prelude is on the chat; the task reads the
chat.

Only the player's lines, because the Room's own would come back to it as if
the player had said them. Only lines from before begin, because everything
after it is ordinary room conversation about a story that is already running,
and handing the room's whole later history back as a launch instruction would
let a conversation on turn 90 rewrite the story's ground.

## 6. The seams

| What | Where |
|---|---|
| The pause, the setup, the wants | `story/prelude.py` (`SETUP_KEY`, `PRELUDE_KEY`, `awaiting_begin`, `begin_story`, `player_wants`) |
| The location draft, its four operations, the review, the record | `story/location_design.py` (`DRAFT_KEY`, `PASS_KEY`, `set_skeleton`, `set_charter`, `check`, `submit`, `submitted_plan`) |
| The tools | `story/room_tools.py` (`draft_location`, `draft_charter`, `review_location`, `submit_location`) |
| The two new regimes and their budgets | `agents/story_planner.py` (`run_prelude`, `run_location_plan`, `room_town_planner`, `PRELUDE_STEPS`/`PRELUDE_WALL_SECONDS`, `LOCATION_STEPS`/`LOCATION_WALL_SECONDS`, `LOCATION_LORE_CHARS`, the wall/steps tables in `run_planner`) |
| The seam it lands on | `world/charter_generate.py` (`plan_specification`, `propose_town`'s `model_call`), `world/charter_runtime.py` (`generate_lived_location(town_planner=)`, `_plan_lived_location`, `closure_inputs`) |
| What the opening hears | `agents/story_planner._opening_task` (`player_said`) |
| The greeting launch's cut | `story/greetings.start_story` (`prelude=`) |
| The routes | `web/app.py`: `prelude` on `POST /api/characters/{id}/start`; `POST /api/chats/{cid}/prelude`; `POST /api/chats/{cid}/begin`; `awaiting_begin` on the chat read; the 409 in `turn_new` |
| The card | `prompts/story_planner.txt` (THE PRELUDE, THE LOCATION, and `player_said` in THE OPENING), English and Japanese |
| The launch screens | `static/js/editors.js` (`quickStartModal`), `static/js/app.js` (`renderWizardScenario`/`runWizard`, `wizardFromScratch`) |
| The waiting story | `static/js/chat.js` (`renderChat`'s banner, `beginStory`) |
| Tests | `tests/test_room_prelude.py` |

**The composer is refused, not auto-begun.** `turn_new` answers 409 while a
story is waiting. Begin generates a lived-in place and can take a minute; a
player who typed a line into the composer asked for a beat, not for a town.
The client hides the composer behind the begin button, so the 409 is the
floor under that rather than a path anybody walks.

## 7. What is left

- **The one-shot is still reachable, and should probably not be.**
  `propose_town` without a `town_planner` still sends `_PLAN_SYSTEM` to the
  `utility` role, and two callers still take that path: `POST
  /api/chats/{cid}/charters/generate` used mid-story from the settings and
  lorebook screens, and the Room's own `request_location` package operation.
  The owner's instruction was scoped to the quick starts and that is what
  landed; whether the mid-story paths should route to the Room too is a
  decision, not an oversight, and the Room calling a `utility` model to do
  its own job through `request_location` is the odder of the two.
- **`narrate_actual_history` is the last `utility` call on this path**, and
  it narrates what the presimulation actually produced rather than authoring
  anything, which is a different job from designing a place. It is already
  guarded -- a failure costs the prose and the simulation stands -- so it
  cannot fail a launch the way `propose_history` did. Left where it is.
- **Unmeasured live.** Nothing here has run against a real launch: not the
  wall clock of a 40-step design against the one-shot's single call, not how
  many review round-trips a plan actually takes, not whether the Room submits
  at all within the budget. The opening plan's own first five live runs
  (`DESIGN_OPENING_PLAN.md` § 4a) found three defects in a smaller pass, and
  the same measurement is owed here. `location_plan` is the row to read.
- **Nothing shows the player what the Room did.** `opening_plan`,
  `opening_placements` and `location_plan` are world rows with no reader in
  the browser -- the gap `DESIGN_OPENING_PLAN.md` § 4a opened and did not
  close, now one row wider. After a prelude the player answers a question,
  presses begin, and sees a story.
- **The prelude cannot be re-entered.** A story that began is begun; there is
  no "hold on" once the button is pressed, and no way to take the prelude on a
  launch that did not ask for one.
- **The four location tools ride every reply's system block.** The tool table
  is the largest and most cacheable thing the Planner reads (15.6k characters,
  measured 2026-09-04); these add to it on every ordinary room reply, where
  they can only refuse. Filtering the manifest by regime is the obvious fix
  and was not done, because `system_block` is shared and the saving is
  unmeasured.
- **A Japanese location pass is unchecked.** The card's paragraph landed in
  both packs and the pass runs inside `story_language_scope`, but its product
  is a plan object rather than prose on a page, so no render, no test and no
  reader would notice an English plan on a Japanese story. The UI side IS
  closed: the twelve new strings are in both catalogs, and
  `PRELUDE_FALLBACK_LINE` is carried in `static/js/writers_room.js` for the
  harvester the way the room's other engine-spoken lines are, with
  `tests/test_room_prelude.py` holding the two spellings together.
