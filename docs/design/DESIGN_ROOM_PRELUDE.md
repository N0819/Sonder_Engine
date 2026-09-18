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

**The review closes WITHOUT the prehistory, and the launch closes with it.**
`propose_history` runs after `propose_town` and takes the finished plan as
its input, so there is no history to hand the checker while the plan is still
being drafted. A plan that closes clean under review and fails under the
launch's `close_plan(history=...)` is therefore possible. It is the one
difference between the two, it is named here rather than papered over, and
it has not been seen.

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
- **The location's PREHISTORY is still a `utility` call.**
  `propose_history` sends `_HISTORY_SYSTEM` to the same role, on the same
  launches, immediately after the Room has designed the place. The owner
  named the town-design prompt; this is its sibling and the same argument
  would appear to apply to it, but it was not asked for and one-shot JSON is
  a better fit for it -- the months behind a plan that already exists is a
  smaller and more closed question than designing the plan. Worth a
  decision, not a silent change. `narrate_actual_history` is a third.
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
