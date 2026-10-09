# The prose contract: an author that writes, one encoder that builds

**Status: THE DIRECTOR (2026-09-27).** Begun as an experiment on 2026-09-22
(branch `worktree-jev-prose-director`), behind a `director_contract` setting
beside the causal ledger contract
([`DESIGN_SPECIALIST_CONTRACT.md`](DESIGN_SPECIALIST_CONTRACT.md)). On
2026-09-27 the causal contract, its five specialists and the setting were
deleted: this is the only Director. What it does not yet do that the causal
one did is `docs/UNBUILT_PIPELINE.md` § 1.1.

## Why

The causal contract made state tracking work. It did it by making the
Director two things at once: the author of how a beat realistically unfolds,
and its dispatcher, which meant cutting spans, allocating item handles, and
routing every row to channel categories under a 12 KB sheet. Five hands then
re-read those rows positionally, with a forwarding round and a recompiler to
reconcile them. The owner's observation that motivated this branch: the
tracking works, but making the model track everything cost it the ability to
play author. The narrative lost its flow.

A shorter output contract does not fix that, because the job is still
dispatch. This contract takes dispatch away from the author entirely.

## The contract

For both `director_interpret` and `director_resolve`:

1. **The Director writes prose** (`prose_contract.director_<stage>` card,
   role `director`, step key `director_prose`). It resolves the beat as an
   objective account, with wide latitude to add detail and carry consequences
   as far as they would reach. It has two limits: a declared act is not
   replaced, and another mind's choices are its own. The rest of the sheet is
   habits that make prose buildable (order, exact quotes, one name per thing,
   where bodies end up, how long things take), not rules.
2. **Jev picks the tools** (`llm/decisions.py`: TypeSafe's decision model on
   OpenRouter's `/api/alpha/decisions`). One `noul` question per channel the
   story keeps and the stage serves (`jev_questions.<channel>`), all asked
   at once against the prose, the cast names and the known rooms. A channel is
   granted when its yes-probability reaches `prose_contract_threshold`
   (default 0.3). Jev writes nothing, so it cannot start authoring. It
   **fails open**: if Jev is unreachable, every candidate is granted.
3. **One encoder does every hand's job** (role `encoder` -- named
   `director_specialist` until 2026-09-27, and a setting stored under that name
   is read as the encoder's, `providers.RENAMED_ROLES` -- step key
   `director_specialist`). Its sheet is a small core plus the granted
   channels' **existing, unmodified** chunks. The core tells it how to read
   those chunks' several-hands vocabulary. Its payload is the prose, the
   Director's own inputs, and the union of the world slices the granted
   channels' owners would have received, so it binds existing things by
   their keys. It writes the beat as **ordered events**, each carrying its
   transforms. It also spans: one event per causal step, and every spoken line
   is its own event.
4. **Code converts.** Position becomes `chrono_id`. Each distinct item name
   gets one handle. Categories come from the channels actually written, plus
   `speech` and `attention`. The rows then enter `normalize_causal_ledger`
   exactly where the causal Director's did. The transforms are split by channel
   owner and handed to `_run_specialists(answer_for=...)`, so the binding,
   patch validation and fold that judge a hand's work judge this too. Every
   floor after the fan-out runs unchanged.

With one writer, the encoder's output order is the chronology. No forwarding
round runs, and nothing is reconciled across hands. The global compile still
runs; with a single source, it is only in-order application.

**Widening.** If the encoder names a tool it needed and was not granted
(`missing_tools`), the engine grants it and asks once more. That answer
replaces the first; nothing is merged. `prose_contract_widen = 0` turns this
off.

## What is kept and what is replaced

| Kept | Replaced |
|---|---|
| Stage outputs: `ledgers`/`sequence`/`causal_ledger`, `state_diff`, `state_assertions` | The causal Director sheet (`causal_director.txt`) at both stages |
| `normalize_causal_ledger`, the authority checks, every post-fan-out floor | Director-authored spans, item handles and categories |
| Bind, validation and fold in `_run_specialists` | Five parallel hand calls, forwarding, positional reconciliation |
| Channel rules (the encoder's own card since 2026-09-24) | `_dispatch_specialists`' gates, as the predictor of which tools a beat needs |
| Commit, perception, narrator | — |

## Where it lives

- `agents/director_prose.py`: the contract (`run`, `dispatch`, `ledger_from_events`).
- `llm/decisions.py`: the Jev client (`decide`, `OVERRIDE` for tests).
- `llm/prompts.py`: `prose_director_prompt`, `unified_specialist_prompt` (the
  encoder's sheet, from its own card), `encoder_parts`, `jev_channel_questions`.
- `llm/schemas.py`: `ProseDirectorOutput`, `UnifiedEvent`, `UnifiedSpecialistOutput`.
- Cards: `prose_contract/*.txt` (the Director's sheets, the room designer);
  `encoder/*.txt`, the encoder's own card -- its core, one chunk per engine
  channel, and `<channel>__<part>` parts for the rarer changes inside the big
  channels; `jev_questions/*.txt`, one decision-model question per channel
  and per part. English and Japanese.
- `agents/director.py`: the two call sites and `_run_specialists(answer_for=)`.
- `tests/test_prose_contract.py`, `tests/test_the_encoder_has_its_own_card.py`.

Each stage's record persists at `orchestration.prose_contract`: the prose,
Jev's probability per channel, the selection, encoder timings, any widening,
and the raw events.

## Known gaps

- **What the causal Director did that this does not yet do** is
  `docs/UNBUILT_PIPELINE.md` § 1.1 (the list was made when the causal path
  was deleted, 2026-09-27, by porting its tests).
- **Extension specialist families are gone.** `add_director_specialist`
  raises since 2026-09-27 (`docs/guides/EXTENSIONS.md`); their sheets were
  never built from engine chunks, so this contract never ran them.
- **The encoder's card is a fork of the hands' chunks** (2026-09-24). It
  used to read the causal chunks verbatim, behind a core paragraph telling
  it how to reread their several-hands dialect; the owner read the sheet in
  the debug capture ("Seems absurdly long", then "specific prompts for this
  version of the director sound necessary?"), and it now has its own. Since
  the hands were deleted (2026-09-27) it is the only copy of those rules.
  `test_no_record_shape_drifts_from_the_hands` guards the printed record
  shapes and `test_every_ops_field_the_card_asks_for_exists_on_a_hand` the
  `_ops` fields; the prose of the rules has no guard.
- **Establish is out of scope.** The opening turn keeps its own Director.
- **No author-side retries.** The causal Director was re-asked with a
  correction when a must-tick world pressure went untouched, or when an
  authority reading found conduct nobody declared (once, kept only if it
  lowered the count). This contract has neither: a must-tick pressure is an
  input group of its own and a row sourced to it is its tick
  (`tests/test_world_pressure.py`), and the authority readings warn on the
  step and never retry, so a flagged fabrication commits
  (`docs/UNBUILT_PIPELINE.md` § 1.1, item 6).

## Measurements (2026-09-22, chat 153 turns 23/25/26, copies of `engine.db`)

Each stage was rerolled alone (`run_pipeline(only_key=)`) on its own
database copy, so both contracts read identical inputs. The models were the
owner's configured stack (Fireworks GLM-5.2 on every Director role, default
reasoning effort `high`), with Jev on OpenRouter. The harness lives in the job's
scratch directory; `orchestration.prose_contract` on each variant holds the raw
record.

**Wall clock per stage, final configuration** (threshold 0.5, sharpened
questions, record pre-filter, `already_happened`, widening fix, encoder
`reasoning_effort=off`):

| | turn 23 | turn 25 | turn 26 |
|---|---|---|---|
| interpret, causal | 59.7 s | 13.1 s | 64.8 s |
| interpret, prose | **12.6 s** | **10.2 s** | **11.9 s** |
| resolve, causal | 43.4 s | 13.6 s | 32.0 s |
| resolve, prose | **34.5 s** | 19.6 s | **30.6 s** |

**Where the time goes.** The prose Director's call is shorter than the causal
Director's: 5.7–8.2 s against 5.6–19.8 s at resolve, and 0.7–1.3 s against
5.1–18.3 s at interpret. Jev takes 0.21–0.44 s and costs about $0.00002 for
the whole 38-question battery. The encoder is the rest.

**The encoder's cost was reasoning trace, not the single call.** At the
default `high` effort it wrote 12–20k output tokens per beat, one run hitting
the 50k ceiling, against a real answer of about 1.5k tokens. Resolve took
102–198 s. `low` barely moved GLM (46–60 s). With `off` it writes 1–2.4k
tokens in 3–11 s. **The encoder's reasoning is `off` unless the host sets
it** (`providers.ROLE_DEFAULT_EFFORTS`), and since 2026-09-27 its row on the
models panel says to use a model that does not reason. The encoder
transcribes a decided account; the thinking happened in the Director.

**Jev routing.** With the first question wording and threshold 0.3, it granted
13–18 channels per resolve beat. The questions matched words, not record
classes: `public_evidence` scored 0.76–0.85 on every beat with dialogue, and
`contact_action_ops` 0.84–0.94 because the prose described room-wide vibration.
Three changes brought it to 3–9 channels:
- each question now states its class and its complement ("Answer no when…");
- channels that can only act on a standing record are asked only when that
  record exists (`_RECORD_FACTS`);
- the threshold is 0.5.

Replayed against six stored beats, the 0.5 selection still covered every
channel the encoder went on to write, except on one beat where the causal
contract wrote nothing either. Live, widening fired on 2 of 3 resolves and
cost about 10 s each.

**Fidelity.**
- Interpret wrote the same channels as causal on all three turns.
- Resolve wrote a superset of causal's channels on turns 23 and 25, and on
  turn 26 every causal channel except `poses`.
- Two defects were found live and fixed before the final round:
  - the Director wrote past a player-asserted landing (`already_happened`);
  - a widened re-ask returned only the events its new tool touched, and the
    replacement dropped the rest of the beat (`previous_events`, plus a
    thinner answer never replaces the first).

**Authorship, read as fiction.** The prose is concrete and consequential. The
Director reconciles a character's declared line with the world rather than
editing it: *"'…she's in flight.' But even as he said it, the console room
shuddered underfoot…"*. With the latitude this contract gives, it also runs
ahead. On turn 25 it landed the ship, one beat before the player wrote that
the ship "begins to land". Whether to pace it is an owner decision; nothing
here clamps it.

**Not measured yet:** more beats, other stories, the narrator's page
downstream of each contract, and repair and correction rates over a long run.

## Situations (2026-09-22/23, 13 beats, four stories)

This round covered chats 153 (the Doctor), 137 (Mirelle, NSFW; Fireworks
GLM-5.2-fast on every Director role), 123 and 120. Each beat ran in three
arms: causal, causal with the hands' reasoning off, and prose with the
encoder's reasoning off. There were 78 runs and no errors.

**Median wall clock:**

| Stage | Causal | Causal, hands off | Prose |
|---|---|---|---|
| Interpret | 19.1 s | 16.0 s | 12.5 s |
| Resolve | 62.7 s | 34.0 s | 29.1 s |

**Fixes found live** (both contracts unless noted):
- **A body `inside` another body is its interior.** `canonical_enclosure_mode`
  runs at containment ingest and is resolved against the holder. The
  materializer mints a place only for `interior`, and the sheet teaches
  `inside`, so a swallowed body was concealed but never placed.
- **A room is never a `positions` key** (`drop_room_keyed_positions`).
- **Code closes the dependencies it can prove** (prose contract only). A
  `movement` implies `positions`, and a destination no scene room holds
  implies a place is needed.
- **Jev questions state what they would otherwise miss.** The inside of a
  body is a place (the swallow's `positions` went 0.15 → 0.97), and a body
  carried, held or swallowed is still present (`cast_changes` had marked the
  player dormant).
- **The authority checks were all false positives on prose.** All six
  warnings over the 13 beats were one of three things: the player's body as
  the grammatical subject of something done *to* it, a simile, or an
  involuntary response. They warn on prose and never retry.

## The room designer

Rooms are designed by their own agent (`agents/director_rooms.py`), which
runs beside the encoder. It uses the Writers' Room loop protocol: each step
returns tool calls, code runs them, and the results come back in the
transcript. Its tools:
- `inspect_rooms`: any standing room whole -- its stored record and its
  drawing (the rooms around the place arrive as `surroundings`, their
  records in `rooms`);
- `draft_room`: builds the room in pieces;
- `view_room`: the draft drawn on the engine's own cell grid, north up, with
  what the engine made of every fixture, and collisions shown;
- `check`: the real merge plus `room_layout_lint`, owed rooms, unplaced and
  overlapping fixtures;
- `submit`: refused while the check fails and steps remain. `done` is held
  to the same rule since 2026-09-27.

`draft_room` merges; an `adjacent` entry `{"to": ..., "drop": true}` takes a
doorway out of the DRAFT and never out of the world.

It works to the engine's own division of labour:
- **Planned rooms.** The Writers' Room plans a room. A beat that enters it has
  the room *developed* under the plan's id. The purpose and exits stay; the
  contents are the designer's. Jev answers "does the passage enter X?" for
  each planned stub in reach, in the same one battery.
- **Invented places.** A place no plan holds is invented by the Director in
  three simple fields: `name`, `size`, `shape`. An id is reserved before
  either worker starts, so the encoder places bodies into it at once.
- **Reconcile.** Afterwards the designer makes one short call naming any of
  its features that the encoder also wrote as objects. The pairwise Jev check
  this replaced removed a TARDIS's central console.

**Measured (chat 153 turns 7–8, chat 137 turns 9 and 45):**
- The designer runs 7 steps and 7–12 tool calls, taking 34–72 s. That
  outlasts the encoder, so place-entering resolves took 48–94 s.
- The final check was clean on 3 of 4 beats. The fourth submitted over a
  size/extent disagreement, which is why `submit` now refuses.
- The treatment room developed from its plan came out at 5×4 paces with
  seven fixtures, each with footprint and height, and the doorway on the
  plan's wall. It also showed two fixtures hidden under others, which is why
  collisions are now drawn and checked.
- Caps are `MAX_ROOM_STEPS = 8` and `MAX_ROOM_SECONDS = 150` (named).

### What a model step is no longer spent on (2026-09-27)

Traced whole on the betrayal replay's yard (plain GLM 5.2 on NanoGPT,
reasoning off), the designer took 42-48 s and all eight steps: two
inspecting the rooms around the yard, one looking again at a plan it had
just been shown, and three on contradictions the check would have named the
step the yard was drafted -- a size word its extent disagreed with, a
doorway on a wall another doorway held, and a placement that laid the yard
over the barracks. The step cap stopped it, "clean" only because the engine
had dropped the bearing from both doorways on that wall. None of that needs
a model, so code and the decision model take it:
- **`surroundings`**: the standing rooms around the places being designed,
  handed over already inspected -- plan exits, rooms with a doorway into the
  place, the rooms the beat's bodies stand in and their neighbours past
  anything but a wall (`ROOM_SURROUNDINGS = 6`). A plan's stub nobody has
  entered is not drawn (shown empty it reads as work: one run developed
  seven of them in its first step) but still counts as space below.
- **`placing`**, for each place the Director invented: the floor area its
  size word covers, and `doorways_that_fit` -- every free wall of those
  rooms where the place's doorway joins the world, tried by merging it there
  and asking `room_layout_lint`, at the size's square and its two longest
  shapes, rejecting any try that loses a bearing anywhere (the silent drop
  above). A wall with any neighbour on it is never offered, a solid one
  included: the lint lays out only what a body can pass through, so a room
  behind a wall is invisible to it (`ROOM_PLACEMENT_SECONDS = 1.5`). The
  offer is where the place CAN join those rooms, never where it must: told
  to take "one of" them, a designer hung a harbour café off the theatre's
  stage-door vestibule because that is where the cast had been standing.
- **The check runs itself** after every step that changes the draft, and
  every check first sets each size word to the one its extent measures (the
  extent decides; the word is only ever its label). When the check says a
  new place stands where it cannot, it hands back the `doorways_that_fit`
  the place **as drafted**; when a drafted wall is overfull, its arithmetic
  (`crowded_walls`: the wall's length, which side of the extent that is, the
  paces each fixture on it takes -- "needs 7, has 5" had a designer widen
  the wrong side twice). Calls past a step's cap are named back as not run.
  And it names a new place the DRAFT joins to nothing (`no_way_in`: no
  doorway but a wall, no `parent_entity`, no `zone`): the merge would open
  it onto the room the bodies stood in (`connect_orphan_new_rooms`), which
  is the engine's floor and usually the wrong street -- a harbour café
  would have opened onto a theatre's rehearsal room.
- **The ids given are fixed**: a new id whose name folds to an owed place's
  name (accents off, case folded) is drafted as that place -- `harbour_cafe`
  against the reserved `harbour_caf` built the café twice. A standing room
  is never taken over this way.
- **Jev says when it is finished.** With the check clean and a description
  on every owed room, two questions per room against the prose and the
  room's record (`prose_contract.room_done_missing`: a part of the place the
  record never mentions; `room_done_unlisted`: someone placed at a feature
  that is not a fixture). Under both bars (`ROOM_DONE_BARS`: 0.5 and 0.6)
  the design is finished and no step is spent saying so; a prepared design
  can finish before the first step. Otherwise what may be missing comes
  back ONCE, saying to submit if the record already holds it -- a note
  repeated every step was chased: the designer wrote "this is where Luca
  stands" into a fixture to satisfy a reading the grave already answered.

Measured on the yard and five recorded cases from three other stories,
old loop against new: [`ROOM_DESIGNER_SPEED_2026_09_27.md`](../experiments/ROOM_DESIGNER_SPEED_2026_09_27.md).

### The rooms in question, and rooms prepared between turns (2026-10-08)

Measured on the Brackwater run (chat 166, 30 beats; the record is
[`PLAY_2026_10_07_brackwater.md`](../experiments/PLAY_2026_10_07_brackwater.md),
Addendum):
- **`rooms` is the records of the rooms in question, not the town.** The
  spatial slice carried every room the world holds: 26.2k chars of a 75.3k
  in-beat payload, while `inspect_rooms` was called 0 times in 49 steps.
  Every room id a design wrote was already on `world_index`, in
  `surroundings`, owed, or named by a plan's exits, and of 91 field values
  its drafts wrote none came only from a room left out but the light word
  `dark`. So `_groundwork` keeps the stored records of the drawn rooms in
  `surroundings` -- the drawing leaves out a room's storey, light, surface,
  exposure and region and a doorway's way and name, which is why dropping
  these records was refuted -- and of each owed room that already stands (a
  plan's stub holds the plan's measurements): 7.3k chars on average, about
  5.2k tokens fewer a call. Every other room stays on `world_index.elsewhere`
  (name, storey, exits, ways), and `inspect_rooms` now hands any room over
  whole. An unentered stub is left out as it is from the drawing.
- **Rooms prepared between turns are off by default**
  (`prose_contract_room_predevelopment`; `1` turns them on). 131 out-of-band
  designer calls (1.76M prompt tokens, 0.57M uncached; 51k response; 964 s)
  made 25 designs, at least 19 of which never seeded a beat; every seeded
  design was judged unfinished on first look, and on the one matched pair
  the seeded runs took 7 and 6 steps where the unseeded took 3. Off, no
  cached design seeds a beat either. On, a brief is designed once: every
  attempt is filed under its brief's fingerprint, a design whose check
  failed is kept as a seed, a design is kept while its room is still the
  plan's stub wherever the player stands, and what a seed's first look found
  -- its check, or what the prose puts in the room that its record does not
  hold -- is the first thing the in-turn designer reads.
- **Superseded the same day: rooms in view are BUILT before anyone walks
  in, on by default.** The owner's ruling (2026-10-08): "Between turns, each
  planned room the player can see into or is heading for is designed once
  and put into the world, so it exists before they walk in and the view
  through a doorway has something real in it. This replaces the hidden-draft
  predevelopment and is on by default." The hidden draft's failure was where
  it was READ -- only by a beat that entered the room, against that beat's
  prose -- not that it was made. Now:
  - *Whose rooms*: every actor's, not only the player's. The owner chose it
    the same day ("Rooms in view of, or ahead of, ANY cast member get built,
    bubble travellers included, not just the player's" -- light plans far,
    heavy builds near the actors). Each frame's commits run that frame's job
    (`predevelop_job_key`) over `actors_ahead`: the players first, then
    every cast member the frame's scene places. A causality bubble places no
    player, so its job serves its travellers, and its own beats -- which run
    the pipeline -- build the rooms in at its next beat: with no prose
    contract at a bubble's interpret, the stage's own assertions carry them
    (`carry_installed_rooms`). The bound is per frame, the players' rooms
    first within it: one bound for the chat would make a traveller's rooms
    wait behind every beat the player's view had work, a freeze in the
    owner's sense (`OFFSCREEN_BEATS_ARE_UNCAPPED`).
  - *What is built*: the actor's room, the next leg and the end of a walk
    under way (`scene.approach`), and every room sight reaches through a
    doorway (`structure.rooms_in_view_or_ahead` over
    `visible_adjacent_rooms`, perception's own answer). A room behind a shut
    door is neither seen into nor headed for until someone opens it or sets
    off for it; the brief a beat is handed (`rooms_to_develop`) still
    includes it, so a beat that opens the door designs the room as before.
    Nor is a frontier space the plan holds open (`rooms_to_build` drops
    every `structure.provisional_room_ids` stub): its name is the grammar's
    and its purpose often empty, built from that name it is spent -- a
    claim keeps the name of a room with prose and its purpose never reaches
    the room -- and the Writers' Room plants ahead exactly there (owner's
    ruling 1, the same day). It stays a stub until a plan claims it, and a
    beat that enters it first still designs it in the beat.
  - *Prepared out of band, installed in band.* The commit tail's job
    (`schedule_room_predevelopment`, at most `PREDEVELOP_PER_TURN` = 4 a
    commit) writes its cache, never the scene, and files each design the
    moment it is made. The next beat's `director_interpret` opens on the
    scene with every clean design for a stub still in reach built in
    (`install_prepared_rooms`: same brief fingerprint, clean final check,
    the state schema takes it, the layout check still clean against this
    scene together with every room built beside it), so the Director, the
    encoder and any room author read the room and not its stub; and its
    prose contract puts the rooms in the beat as its first event
    (`with_installed_rooms`, `room_event`). Perception previews that event,
    the resolve's planned brief is read off the previewed world (a built
    room is no stub, and no designer is handed it), and the commit persists
    it with the registry projection, the checkpoint and the archive. A
    reroll restores the stub and builds it again, never twice.
  - *The run, the commits and the restore* (the second and third reviews of
    the landing). A design takes about 40 s, longer than a sub-minute beat,
    so a commit that lands while a run designs now asks it for one more run
    on the scene it left (`core.jobs.submit_latest`, decided under the lock
    the run releases its slot under, so no ask is lost, a run that raises
    included); asks fold into one run. Before, the commit joined a run that
    never saw its view. Every write re-reads the cache in one transaction
    and writes only the run's own rooms; a design is kept while ANY live
    frame holds its room as the stub it was made for (`_wanted_elsewhere`),
    since every frame's run prunes the one cache. `restore_checkpoint` stops
    only a run that read a beat it discards (`core.jobs.cancel_from`), and a
    stopped run writes nothing: before, a run designing during a reroll
    wrote its whole in-memory cache over the restored row and the redone
    beat lost the gallery's design. A silent beat (empty input) clears the
    player's declaration and the row establishing its places, which also
    holds every place its stale prose made, and carries exactly the rooms
    the install built in its assertions
    (`director_rooms.carry_installed_rooms`): clearing the row alone
    committed the stub of a room it opened on built, and keeping it whole
    committed the place the prose invented. `orchestration.installed_rooms`
    names only what the stage carries.
  - *A design is taken up again, never begun again*, from where it
    stopped, at most `PREDEVELOP_CONTINUATIONS` (1) times: one whose own
    check was not clean, and a clean one the install refuses. The job runs
    the install's own test first (`_install_test`, the one rule both read),
    merges what would stand into the scene it designs on -- so every design
    and continuation is drafted beside the rooms the next beat builds --
    and seeds a refused design's continuation with the check that refused
    it, the schema's words included (`design_rooms`' `seed_check`; no
    layout check reads those). Refused with its continuations spent, a
    design is filed not clean and waits as a seed for the beat that enters
    the room; no beat's install checks it again. Before the review a design
    refused once was never designed again and was refused at every beat
    after, its room a name through the doorway.
  - *A design that fails is filed and waits* (`failed`, `failed_turn`;
    `predevelop_retry_beats`: `PREDEVELOP_RETRY_BEATS` 2 beats, doubling to
    `PREDEVELOP_RETRY_BEATS_CAP` 16, the Writers' Room's own back-off). An
    unfiled failure was designed again from nothing on every commit: the
    review's probe made 12 calls over 4 commits and filed nothing. A run
    that raises outside a design (the actors, the plan's briefs, the
    install's test, a card load) files nothing and is recorded failed on its
    job; it makes no model call, and an ask made while it ran still gets its
    run (`core.jobs._run`).
  - *The between-turns note* (`prose_contract.room_prepare_note`, en and
    ja) says no beat has described these rooms yet, never that nobody is in
    them -- the player's own room is among them, and a stub can hold a body
    -- and says what a draft that already holds a room is. A continuation
    carries no `prepared`, whose card clause keeps a design except where a
    beat's prose says otherwise: between turns there is no prose.
  - *Replayed on chat 166* at turns 3, 9 and 26 (db copy, OpenRouter plain
    GLM 5.2, 52 room-author calls, about $0.22 at list price): the bell loft
    (3 steps, 23 s) and the low walk (3-4 steps, 11-30 s) came back clean
    and were built in; the Gale house came back unclean once (a chair and
    the bed on one cell, at its 8-step cap) and clean twice (3 and 7 steps,
    the second spending five on one table and one bench); the open
    water's first design broke the plan's own bearings at the cap and its
    continuation came back clean in 6 -- and was still refused, because its
    doorway and the built low walk's took the same cells of the landing
    stage's east wall. (The open water is a provisional frontier stub, which
    the job now leaves to the Writers' Room; the class -- two designs each
    clean alone -- is what the job's own run of the install's test now
    takes up.) Through the bell loft ladder the player's view went from
    "the bell loft." to the loft itself; the Gale house door from "the Gale
    house." to the house; Hester's view on the landing stage from the low
    walk's name to the walk (the player faced away from it).


### Where along the wall, and where a place joins the world (2026-10-08)

The owner's procedural-generation choice of 2026-10-08, lane one: a model
decides what a place holds and which wall each thing stands against; code
decides where along it. Built in `world/spatial_pack.py` (behind the
`world/spatial.py` facade) and `agents/director_rooms.py`, inside the one
`design_rooms` loop that the in-beat designer and the between-turn job that
builds rooms in view (`_predevelop_run`) both run. The install
(`install_prepared_rooms`) runs neither the packer nor the doorway rules: it
checks a design the job already packed (`_install_test`), and one the world
has since moved under fails that check and stays a seed -- for the beat that
enters the room, or for the job's next run.
- **The packer.** After each `draft_room`, and at every check, a fixture
  the draft places keeps its seeded cell when that cell is free at its
  height; otherwise it takes the free place nearest its seed ALONG ITS OWN
  WALL (`offset`), or, for a corner or a fixture with no wall, the nearest
  free cell (`cell`). Every place is tried by the engine's own placement, so
  runs, large footprints, lanes, shaped rims and shared corners come out as
  drawn. The longer fixture keeps its seed when two collide, fixtures drafted
  together are laid end to end when a seed leaves no gap, and a fixture a
  plan has shown is settled -- never moved for a later one (`_pack`'s
  record). Standing fixtures and every place the designer wrote are
  obstacles. A wall that cannot hold its fixtures at one height is never
  emptied onto another wall: the check hands back ONE line per wall and
  height with the arithmetic and where each stuck fixture would fit
  (`crowded_walls`), and the choice stays the designer's. The card offers
  `offset` for a fixture or doorway the prose fixes along its wall (en and ja).
- **The wall count per height.** The check counts a wall per height along
  its rim, a large fixture's inward row being floor (`wall_loads`;
  `DESIGN_ROOM_FIDELITY.md` §3).
- **Doorways.** A whole open side holds any other opening; two new doorways
  seeded onto one cell get distinct places along their wall
  (`doorway_places`), never a doorway the world holds and never one whose
  place the designer wrote; a level doorway written from both rooms with
  bearings that are not opposites takes the owed place's bearing on the far
  side -- never a doorway the world already holds, from either side
  (`_world_holds_doorway`: re-bearing the far copy made a one-sided
  re-declaration of a settled door a matching two-sided one, which the
  merge's shield lets through, and the door moved walls), never a far copy
  whose place along its wall the designer wrote (turned to another wall, a
  door a fifth of the way along a house's east wall became one a fifth of
  the way along its north wall), and never where that would lay one room
  onto another. Such a pair is left as written, and the merge keeps neither
  bearing, as it always did. A way up or down written from both ends in the
  same direction is NAMED, never resolved -- the merge keeps neither
  direction, and the bearing row it left behind had a designer flipping n
  and s. Whether code may give a doorway the world holds WITH NO BEARING its
  first wall this way is the owner's (`DERIVE_FAR_SIDE_OF_A_HELD_BEARINGLESS_DOORWAY`,
  off).
- **The doorway search offers only what the check passes, and finishes.**
  It reads the check's own walks of the world once (`layout_index`; the
  world as the merge holds it, since what the merge does to the world itself
  it does to every trial), lays each wall's new place against them
  (`leaf_rows`), and confirms a wall that passes with one real merge, judged
  the same way. `leaf_rows` gives the whole check's VERDICT -- whether the
  room brings a row the world does not hold, but about its own interior --
  or says it cannot and the whole check answers; its rows are the walks'
  evidence for the verdict, which can name a pair the other way round or
  leave one of the check's own rows out, never the check's rows. A place
  whose id sorts before its host's walk starts a walk of its own and re-lays
  the host's part of the world, and so does a doorway onto a room the walk
  could not place: where the host's own walk re-reports a standing
  collision, every wall of that host is refused at once, and where it
  re-reports none, the whole check answers. A place laid first that would
  run ahead of a walk started between it and its host, and a place another
  room's doorway already names, are left to the whole check too. Taking
  every row naming the place for the whole of what it adds -- the first
  build -- offered walls the designer's check then refused with a row about
  two standing rooms that no refit could clear. On a host standing on a
  site plan the merge may stand the place on that plan as well, and two
  rooms one plan places are where it put them, never a collision -- so a
  wall the walks refuse there is put to the merge before it is refused. The
  search tries first the rooms the draft and the prose name
  (`_named_in_prose`), never offers the inside of a body or a thing, and
  names the rooms it ran out of time before trying (`not_tried`).
- **One reading of the world a run.** A design run reads the world's own
  rows once, merges its draft once per change for every pass of every
  check (`_Reading`), and takes a refused far side or doorway batch back
  once, until the draft's layout changes (`_layout_key`).
- **A draft the merge cannot take goes back to the designer.** Every pass of
  code's own -- the far sides, the doorways, the packing, the plan drawn
  after a draft or a look, an inspection -- does nothing to such a draft,
  and the check hands the merge's error back, as it always did
  (`_merge_or_none`). Raised out of a pass instead, it ended the whole
  design run, and the beat lost every room the designer was building: a
  doorway written as one object rather than a list of them, or a
  `parent_entity` written as an object.
- **A collision found again.** A place that starts a walk of its own
  re-lays its part of the world, and a collision the world already holds
  can come back reversed or via another room -- a row about two rooms the
  draft does not hold. Whether that is the same collision, compared by the
  two rooms it names alone, in every comparison the check makes (the
  commit's once-told warning, the designer's check, the search), is the
  owner's (`spatial_lint.LAYOUT_COLLISIONS_COMPARED_BY_PAIR`, off).

**Measured, offline, on the 2026-10-08 play database** (the designer's 33
in-beat runs of chats 154-166, replayed through the real loop with each
run's recorded first answer and no model): clean first drafts 16 of 31 ->
24 (11 places written by code in 8 runs; over-full wall rows 12 -> 3: the
elevator shaft's west wall at full height, where two full-height runs --
one of them the shaft's own concrete -- are reported rather than packed,
and the inn's two walls the prose over-filled at waist height); clean final
drafts 29 of 33 -> 32 (chat 160 turn 11's two corridor positions and chat
165 turn 3's long table and bench separated along their walls, and chat 166
turn 22's open-side rows gone). Loop time over those runs, the doorway
search left out, measured under one load: 10.3-10.7 s before, 6.6-6.8 s now
(14.4 s for the first build). A check's passes on chat 166's turn-22 final
draft: 0.75 s for the first build; now 0.35 s for the first check, 0.005 s
for the same draft again, 0.12 s after an edit that moves no room (the check
alone, before: 0.18 s).

The doorway search on chat 166's 33-room turn-22 checkpoint: 0.19 s a try
and 2 of 12 walls offered before; now 2.6 ms a screened wall and 48 ms a
confirming merge, all 13 walls in about 0.9 s with the Gale house (named in
the prose) second, nothing left untried; the slowest of the seven recorded
in-beat searches is that one and the median 0.37 s (chat 160's turn 2, whose
one host of five stands on a site plan, 0.37 s against 0.32 s before its
refused walls were put to the merge). Against the old search
(every shape merged and put to the whole check), with no deadline: on the
14 recorded searches, the old 343 walls exactly, plus 50 on chat 160's turn
2, where the old search offered none at all; with every room of six
checkpoints a host and place ids sorting first, last and as recorded (18
searches), the old 1,169 walls exactly, plus 160 on chat 160's turn 2.
There the world held a doorway onto the docked lift car's inside that the
merge strips on its own, which read as a bearing every wall "lost". Every
wall offered in all of these gives a clean designer check for every shape
tried. The first build had offered 14 walls the check refused on the
recorded searches, and 20-24 of chat 166's town with every room a host. On
74 seeded random towns, every room a host and place ids sorting first, in
the middle and last (the groundwork path), or a place drafted with a bench,
half the time beside a standing room drafted at a new extent (the refit
path): the old search's 5,674 walls exactly, none lost and none gained, each
passing the designer's check. In 30 of those towns three ways in ten go up
or down, and 8 of them stand on a site plan; judging a place without the
site the merge would give it had lost 7 of those walls before a refused wall
on a sited host was put to the merge.

**Live, one replay** (chat 166 turn 22 on a database copy, OpenRouter
`z-ai/glm-5.2`, 8 designer calls and 1 decision-model call, about $0.03
by the ledger, before the review's fixes): the capture filed each step's
own draft (4 distinct drafts in 8 steps; before, one draft hash for every
step of all 29 multi-step runs); the groundwork offered 13 walls in 0.9 s;
the packer had nothing to move; the design ended clean at the 8-step cap.
Four of its steps went to a stair the designer wrote from both ends as
going up, which the check then misread as a bearing row; that
contradiction is now named instead.

## Playerless bubbles (2026-09-23, `tools/two_lives_drive.py`, rounds 2–8)

Two characters, Emory Vane and Sal Weatherby, each live in their own
causality bubble in the mill town of Aldermill, which is simulated by a
charter, for 12 rounds each. No player stands anywhere: the chat's persona
is never placed. Every model role ran on Gemini 3.8 Flash through
OpenRouter. After each round, every stage of every beat was read against the
others on a copy of the database. Fixes were replayed on a copy of the beat
that found them (`run_pipeline(from_key=)`) before the next round ran. What
each round turned up, and the class it was fixed as:

**Round 2** (mean beat 71 s against the causal contract's 179 s).
- The aperture was centred on the absent player: it now centres on the
  frame's own cast.
- Charter bodies had twins.
- Pronouns were guessed.
- Charter voices were ranked by name alone: 24 of their lines reached no
  view. A voice is now for someone the beat reaches.
- The identity scrub rewrote a label's own words into the label ("measured
  the middle-aged … measured").

**Round 3.**
- A laid charter body's contacts were dropped at the merge: a body that
  touches something on screen is now stood in the scene and leased.
- A continuing hold aged out on beats that wrote other contact ops: the
  encoder is now told that silence ends a contact.
- Acts were filed to the watching character: every body in view is a source
  the encoder can name.
- "Godidric plants his boots" reached a mind that never learned the name: an
  act's leading own-name is peeled off before the label is applied.
- Six substance adds to a fixture were discarded: a fixture is a destination
  for matter.

**Round 4.**
- 0 of 4 townsperson acts reached the woman watching them. Three causes:
  - the receipt verifier knew no fixtures, so a hand on a lever was read as
    the world refusing the act;
  - a body stood this beat was routed back to the registry and arrived with
    no position;
  - its stand landed in the program's final step, after its own acts.
- A demand the debtor never heard opened a debt.
- `door:<room>` ids reached pages.
- A 21-minute beat turned out to be the laptop suspended.

**Round 5.**
- 30 of 39 townsperson acts and 31 of 42 lines now reached their watchers.
- A regression from standing bodies: the player-room resolver took a
  townsperson for the absent persona, costing 35 model calls and 196 s.
- Every stand rendered as an arrival.
- A charter-backed presence record stood in the room it was introduced in,
  after the charter had walked it away: one body in two rooms.
- A body reached the stand floor under two spellings. It is now keyed on its
  charter identity.
- A noise or a strike un-saw the act that made it. These are now transient
  events; unverified physical channels still hold an act back.
- The encoder copied declared attempts into `observable` where the prose had
  resolved them otherwise. This is now a clause in the encoder core.
- "sayss": an inflected act is now read back to the act in its table.
- The charter registry cache evicted by insertion order. This was the
  test-order flake, and it evicted a hot chat's registry for real.

**Round 6 and after: two defects the owner rejected as nonsense.**
- **One town per era.** Sibling bubbles each simulated their own copy of the
  town. In round 6, 5 of 40 bodies stood in different places in the two
  frames, and a body leased beside one bubble's character was walked around
  by the other bubble.
  - The fix: the town and the Room's story keys (`db.ERA_WORLD_KEYS`)
    resolve to their era's row. A bubble or a couple frame is the same era
    as its parent, and a flashback keeps its own town.
  - A lease names the scene that holds it. Another live scene yields the
    body and may not move it.
  - The charter tick is keyed per era, and bubbles act least-clock-first.
- **Speech at arm's reach arrived as fragments.** In round 5 the smiths'
  replies to Sal did not come through. Three causes:
  - **The cause here was the echo.** `rev_gain` applied a one-pace-relative
    gain to the source-cell level, so every echo read 3.01 dB loud. A bare
    room then fragmented any line spoken more than about two paces off,
    shouts included.
  - **Charter voice volumes.** Every charter voice's volume was stringified
    from its enum name and fell to `normal`, so a whisper was heard like
    speech.
  - **No Lombard effect.** No voice ever rose over its room's noise. Now a
    conversational voice rises 0.6 dB per dB of noise above 45 dB, up to a
    shout (Pearsons et al. 1977). This re-pins the 2026-09-14 launch-deck
    calibration: a normal line at arm's reach three paces from the engine is
    now heard whole.

**Round 7** (median beat 42 s, mean 45 s, 1,084 s for 24 beats; round 6
took 1,579 s). The firewall held on every surface: no townsperson's given or
family name reached either character.
- **Where round 6's 97 s went.** Not townspeople asked again on later beats,
  as first reported: a voice declining to react answers with empty strings,
  and the placeholder-skeleton check counted an all-empty object as a "..."
  skeleton and re-sent it without JSON mode. 21, 28 and 7 extra calls in
  rounds 5-7, about 100 s a run. Found by replaying one beat with every
  stream printed. The owner-approved re-ask rule is held: its premise was
  this guard.
- Voices of one beat now run at once; the provider silence rule is split
  (30 s before the first token, 10 s between, the socket narrowed to match).
- **One town's events.** Stamped with the era, fired where somebody stands
  to meet them, else recorded in the era's own frame; `engine_notices` per
  frame; a place's generated past is history and never comes due (the
  owner's stories fired 179-373 presim rows at their opening commit).
- A regression of round 6's own (conduct refused 5 of 5 when named by the
  body), a phantom absent player costing 11 model calls, a hyphenated
  title's fragment scrubbed out of a room name, a line split around its tag
  delivered twice ("addeds"), and a body still "on the wharf deck" in the
  market square.
- **Sibling bubbles merge** when their people come within each other's
  reach (`perform_sibling_merge`), each side's state carried whole.
- A name carries a trade, not the watch's duty this hour (183 title changes
  in ~100 s of town time); a held thing is the holder's, not "lying here"; a
  doorway's name is mirrored like its barrier; the router is shown what is
  already owed.

**Open:**
- **The author is not shown standing state.** Its payload is identity and
  place (`world_index`), standing positions and contacts, and what already
  happened -- never what a thing's record says. A state the prose asserts and
  the world does not hold is therefore re-invented each beat: the river at
  the wharf stood "four fingers below the weed mark", "four inches", "dropped
  considerably" and "within two feet of the stringers" in four of Sal's
  beats, and `entities` (0.13-0.31) and `world_facts` (0.07-0.14) were never
  granted. A standing-state slice for the author and a reason for Jev to
  record a first-stated state is a change to the contract's own payload, so
  it is the owner's call.
- **Leased and never voiced.** Three deputies stood motionless at the market
  cross for fourteen beats while Sal was one room away: in the aperture, so
  leased and out of the charter's hands; not in her room, so never voiced.
- **Jev grants that come back empty** stay unsettled. On Sal's river beats
  `overlays` scored 0.53-0.66 every beat and nothing was written, which reads
  as the router over-asking rather than the encoder dropping a change.
- **An act is labelled from where the observer ENDED the beat.** Sal faced
  three deputies at the market cross, then walked to the wharf; all six of
  their acts and lines reached her as "the unfamiliar person" (round 7 idx 9;
  round 5 idx 4 the same). The acts were graded at their moment and
  delivered in full -- only the naming failed: the outcome roster and
  display map are built once, from the end-of-beat rooms, and a neighbour
  room with no `dir` is not in them. The fix, traced but not built: roster
  the start rooms of anyone who moved, label each event from its own moment
  (`_as_of`), one descriptor per (observer, body) per beat. Its sibling --
  lines that lost their slot because the tag's comma made them a different
  text -- is fixed.
- A continuing machine noise is sourced to the body that set it going (the
  encoder core's own rule).

**Round 9** ran the sibling merge live: at r4 the two lives came within reach
and frame 1 folded into frame 2 with every carried ledger unioned, nothing
duplicated or lost, the wardens' leases moved. The joint beats it made
exposed four engine defects, all fixed:
- the interaction loop ended a beat on one speaker's closed exchange before
  a listed reactor was ever called -- Sal had no turn on 4 of 8 joint beats;
- a sight line that only grazed one fixture's corner counted as blocked, so
  two people in one room were each "the unfamiliar person" to the other for
  three beats while the shadowcast had them in view;
- the outcome view appended the loop's pre-resolve drafts after its own
  percepts of the same lines, so every line arrived twice and memory kept
  both;
- a contact naming a body by its entity key was dropped at commit, silently.

And the title-word scrub, in its third round (Flume, Reeve, Sluice), was
fixed as a class: a charter's own titles are exempt, read by one function
(`charter_titles`) through one reader both rosters call (`_worn_identity`)
-- the outcome composer had built a second roster that never read the role,
which is why round 8's fix held in act views and failed in outcome views.

## Real engine turns (2026-09-23, the owner's chats)

Five of the owner's chats (153, 137, 126, 120, 122; three NSFW), each
branched a few turns back through the real `turn_branch` route and played
forward with the owner's own recorded inputs through the real `turn_new`
route, so every gate, checkpoint and commit ran as in play. Each new turn is
read beside its source: the same input, played under the causal contract.
Round 1 ran on the host's own models (Fireworks `glm-5p2`) and committed 24
turns before the provider suspended the account at its spending limit;
round 2 runs on NanoGPT's `z-ai/glm-5.2`, the thinking variant for reasoning
roles and the plain one for roles at `off` (the owner's routing).

Round 1, each finding read against the source turn:
- **A body's inside was out of its own reach** (chat 137, a player
  swallowed). The body she was inside never acted in seven beats; the line
  she spoke to it by name reached no one. Three causes: the room designer
  redrafted the existing throat as `quiet: dead`; the player-contact guard
  discarded every interior contact the encoder wrote, as "non-co-located";
  and no reactor rule reached a holder, because every one reads rooms. The
  guard now joins the pair as the scene layer did (`enclosure_joins_rooms`),
  the holder is widened into the beat in the planner and the loop alike,
  and the designer no longer redesigns a place the world holds.
- **The designer redesigned rooms the world holds**: the TARDIS console room
  at both stages (40.5 s + 50.6 s) for doors that are the TARDIS entity's own
  state, which the encoder had already written; the throat on four beats;
  and it wrote a body ("Hinami stands here") and a named owner into anchor
  text, both caught by the composer tripwire.
- **A visible act made with a line was lost** (a blush): folded into the
  speech as a bogus `conditions` transform that alignment dropped, so nobody
  could see it -- and in a second lane re-asserted every beat as
  `cond_hinami_blush_4`, a passing look turned into a lasting state.
  **Muffling was encoded as the speaker's volume**, and a `mutter` from
  inside a throat carried to no one. Both stated in the encoder core.
- **A shed garment read out its record** -- "clothing: yes; worn by: Hinami;
  shed: yes" -- which also named its owner to anyone reading it.

Timing, round 1: 43-169 s a turn. The character call at the host's `high`
took 18-46 s and the narrator 8-21 s; the Director's own share was set by the
room designer on the beats it ran, and by the encoder (5-20 s) otherwise.

**Rounds 2-7** ran on NanoGPT, the routing the owner's as it grew that day:
GLM 5.2 `:thinking` for every reasoning role; the encoder on plain GLM 5.2
(rounds 2-3), then Ling 3.0 Flash (round 4-5), then DeepSeek v4.1 Flash
(round 6 on: "might be better suited for encoder as it is a larger model and
still decently fast"); the room designer, the Writers' Room and `utility`
on DeepSeek v4.1 Flash from round 4. One reroll per turn.

- Rounds 2-3 confirmed round 1's fixes on the beats that found them: the
  player speaks to Mirelle from inside her and Mirelle acts (137 idx 46), a
  blush is an act (126 idx 5). Plain GLM on the encoder still reasoned on
  the real prompt, 140-240 s a call; a DNS outage cost round 3 its tail.
- Round 4 (Ling encoder, 5-41 s a call): the designer redrew rooms the world
  held on six of seven runs, 73-163 s a beat -- it now builds only new
  places, and the encoder keeps only a doorway edit of a held room; a body
  swallowed past the throat fell outside the beat's one-step reach and
  Mirelle was split into a causality bubble of her own -- a body's insides
  and the room it stands in are one reach (both `39192472`). Also a thinking
  model restarting its answer mid-stream, `{"{"prose": ...` (`c7280aaa`),
  `{}` as the whole prose (`67caf1f5`), and a player's quoted line written
  inside its sentence and then discarded as invented speech (`9ea47e1e`).
- Round 5: no bubble split through the swallow. One beat of chat 137 held
  four defects that ran into each other: a character's lines nested inside
  their own `text`, printed on the page as Python dicts; a prose of ",",
  behind which the player's squirm and line were lost; the resolve, with
  nothing of hers to resolve, and the narration moving her into a stomach on
  Mirelle's word alone; and the next beat's encoder placing her in a stomach
  nothing had built, which crashed perception twice (`16141802`, `2849ffce`).
- Round 6: the DeepSeek encoder answered in 3.6-9.1 s, and chat 126 idx 5
  committed in 110 s end to end, the fastest real turn. One turn was lost to
  an intention update naming its goal by text after its repair failed.
- Round 7 (`918980a5`): 19 of 19 turns committed on chats 137, 120, 122 and
  153. The stomach was reserved, built in parallel, parented and entered.
  From the round's own data: the name that reached Vexara every beat was
  traced to the free text of her own pose, which passed no admission gate
  (`e9a1d0b9`); the narrator answered in bare prose on 4 of 13 beats and a
  25-52 s repair re-enveloped it, rewriting line tokens on the way
  (`31cffa45`); two character checks that commit already reads and reports
  were fatal -- an intention named by text (`12a9d213`) and a belief target
  on a non-revise update (`b21936b9`); a walk the prose stated through a
  shut door was refused by a floor built for hands that re-read rows
  (`6bcb76a9`); and a vessel set off with no transit and docked without
  moving, because the sheet asked for a destination the world did not hold
  and said nothing of a place built that beat (`4ff50bf2`, `8c502613`).

- Round 8 (`8c502613`), on the beats rounds 4-7 found broken: 9 of 9
  turns committed. The TARDIS set off `in_transit` with its doorway sealed
  and came in `arriving` over a place the author reserved and the designer
  built (153 idx 23-26); the walk through the shut treatment-room door
  committed, Mirelle drawing it closed behind them as the page says (126
  idx 9); no composer tripwire, no intention or belief repair, and no
  narrator re-envelope on any beat. It found a character's line to the
  player concealed from the player and heard by nobody -- the
  addressee rule now runs on character answers, reading their declared
  audience (`089907a8`) -- and the room designer, at the host's `high`
  effort on DeepSeek, deliberating 140,845 characters over one room
  (1,378 s). Three other beats of 1,589-1,786 s were the host machine
  suspending mid-call (systemd, 21:05-21:31), not the engine: all three
  streams resumed within the same 130 ms and were recovered.

- Round 9 (`36e82840`), with the room designer and the Writers' Room at
  `low` effort in the replay copies (owner: "deepseek v4.1 flash is also a
  chronic over thinker"): 8 of 8 committed, 137-473 s a turn, the landing
  beat that took 1,744 s in round 8 now 149 s. Designer reasoning fell from
  a median of 10,250 characters (max 140,845) at the host's `high` to 3,256
  (max 7,218), and the stomach it built was as whole as round 7's --
  parented, joined by a membrane, anchored, the player committed inside.
  It found a swallowed player's touches all naming the stomach ROOM as their
  target and discarded as non-co-located -- an inside now names its holder
  (`1162ca97`) -- and the narrator's fidelity check calling the player's own
  quoted line invented (`8f2488ae`, a measurement only since E12).

Timing, rounds 6-7: 110-880 s a turn. The character call (GLM thinking)
took 33 s at the median and up to 290 s; the designer 18-335 s, beside the
encoder; the narrator 7-190 s. The prose author ran away to the host's
output ceiling four times in the replays -- 50,000 tokens, 387-522 s each --
and twice in the owner's own play at 40,000 (161-207 s); its legitimate
answers top out at 12,463 tokens. Read from the debug capture, all four
replay runaways were one short sentence repeated with a period of 17-22
characters ("The TARDIS hums. ", "The lamp burns on. "), the band the stream
guard's two loop rules left between them; the short-run rule now reaches
the phrase rule (`774e8f56`), with no false positive among 42,000 stored
outputs.

**Open (real turns):**
- A runaway that rotates paraphrases instead of repeating has no period
  for either loop rule: chat 120 idx 8's prose (round 4) and a character's
  intention note on chat 126 idx 9 (round 8, 184,472 characters, 405 s).
  Compression does not separate it from valid JSON (its best 4 KB window,
  0.265; valid stored outputs reach 0.107), so what bounds it is the
  output ceiling -- per role or the host's -- which is the owner's call.
- The room designer's and the Writers' Room's reasoning effort: both
  inherit the host's `default: high`, and on DeepSeek v4.1 Flash that once
  cost 1,378 s of deliberation for one room (153 idx 26, round 8). At `low`
  (round 9) the tail is gone and the rooms held; the setting is the host's
  (`reasoning_effort` per role), so it is the owner's to make.
- A vessel's transit is written on some runs and not others by the same
  encoder under the same clause: round 8 set the TARDIS `in_transit` then
  `arriving`; round 9, with `entities` granted (p=0.89), recorded the
  departure as sensory events and two beats later called the ship "already
  in flight". Detecting a departure would mean reading prose, so no floor.
- While a vessel is `arriving`, its interior doorway is derived toward its
  last position, not its destination, until the beat that docks it.
- The provider's stream now and then restarts an answer mid-document --
  `{"effects{"effects":` and, later in the same answer, `"tells2{":` -- on
  2 of about 83 JSON calls in rounds 6-8. `_restarted_object` reads a
  restart at the head; garbage mid-document costs a repair (120 s once).
- A host now feels a body inside it (the contact survives) but hears it only
  by the room-to-room sound field, which an interior's own acoustics can
  close; a rule for sound through the host's own tissue is not built.
- The encoder's debt errors: discharging the player's debts on its behalf
  ("'Let's do it' implicitly answers all three"), and "consolidating" three
  open debts into two new ones against the tool's own rule.
- The Director's flourish -- a lamp flickering on most beats -- minted
  `lamp_3` beside `lamp` and `lamp_2` rather than reuse a record.
- A pose note that restates its own structured half reads twice ("kneeling
  over the young woman -- Kneeling over the young woman at the foot of the
  bed").
- Replay divergence is a property of the method, not a finding: inputs
  written for the original timeline do not answer questions the replayed
  characters ask, and the two lanes that diverged (126, 122) read as
  characters insisting on a precondition.

## Played in the UI (2026-09-24, chat 154)

The owner switched Settings to the prose contract (`054893d9`) and played
one beat, turn 4398: the player shut the TARDIS doors as the rotor started.

**"It still seems to be running specialists."** It was not: each stage made
three calls -- `director`, `jev`, `director_specialist` (the encoder's
role, `encoder` since 2026-09-27). But the encoder's
answer is filed through each hand's binding, which records `run`/`ran: true`
per hand, and the step window built its "Written by" bar from that, so the
beat read "prose author, social, objects, spatial". The window now tabs a
prose beat by the calls that ran (writer, channel picker, encoder, room
designer when it started) and names the hands on the encoder's tab as
"engine code, no model call"; each hand's record carries `answered_by:
"encoder"` (`c2227597`).

**"The doors did not close."** They had: both stages set the TARDIS's
`hatch` closed and the dock edge went `closed_door`. But the console room
had been minted on a causal beat (idx 7) with "The doors behind stand open
to the night beach" in its desc, "The open doors' threshold ... the wedge of
moonlit sand visible past them" on an anchor, and bookkeeping in the notes
views render as the room ("parented to the_tardis; minted as ..."). The
player's own view that beat said both "Nothing shows through the shut door"
and the sand past the open doors. `7959ac5f`: one clause in the rooms chunk
-- a place's desc, notes and anchor descs are read as the place every beat,
so they never state a doorway's condition, a thing's state, anyone in it, or
the record -- and the dock edge keeps its bearing when rebuilt (it had lost
`dir: "s"` as it closed). Replayed (153 idx 7-8): the prose room designer
kept the doors' condition out of the room it built (1 of 1) but still wrote
a thing's condition ("the time rotor ... dark and still"); the causal
spatial hand wrote "the pale double doors stand open behind, framing a slice
of moonlit beach" (0 of 1), so its minting sentence now carries the rule too.
Rooms minted before the clause keep their text.

**The encoder's own card.** The owner read the encoder's sheet in the debug
capture -- 32.5K characters for four channels, half of it the `entities`
chunk -- and asked for prompts written for this contract. `encoder/*` is
that card (see Known gaps for the fork). Measured on the 16 encoder calls
round 9 captured (chats 137 and 153, idx 46-48 and 22-26), holding the
payload fixed and swapping only the sheet, DeepSeek v4.1 Flash, reasoning
off, 48 samples an arm:

| | old sheet | native, first | native, final |
|---|---|---|---|
| sheet (every part) | 100% | 75% | 75% |
| events / call | 4.29 | 4.81 | 4.52 |
| transforms / call | 3.44 | 3.33 | 3.08 |
| calls writing nothing | 15% | 10% | 15% |
| obligations written | 2% | 21% | 17% |
| sensory_events written | 17% | 6% | 4% |

With the decision model picking parts, a typical sheet is about half the
old one (the owner's four-channel sheet: 32,543 -> 17,024 characters).
Seconds per call varied 7.7-16.0 between runs of the same sheet, so the
provider's latency, not the prompt, dominates them. Two corrections came
from the fixed-payload runs: the contact chunk had lost its worked example,
and a player pressing her palms to the walls around her was written as
contacts in 1 of 3 samples; restored, 3 of 3. And the core's tools
paragraph had hedged "the only tools granted for this beat, chosen for what
this prose contains" into "one for each kind of change this prose was
judged to contain"; on a long stomach beat the hedged core wrote the
peristalsis's ticking condition 1 of 4 times and the old wording 4 of 4.

**"It is marking everything hinami says as muttered."** Chat 155 (the
owner's Mirelle story), both contracts: the player's soft, embarrassed or
moaned lines to the woman whose hands were on her were written `mutter`
(causal idx 21 and 27, prose idx 30 and 31), and perception gave the woman
a fragment of each ("volume mutter, barrier open, tier within_reach"). Two
writers of it: the prose Director added delivery the input never gave
("Then, quieter, almost a murmur: 'More please.'"), and both Directors read
how a line sounds as how far it goes. Volume is now reach, not sound, in
the encoder, the causal Director (its size bound raised 12,600 -> 12,800 to
hold the sentence, argued in its test) and the writer's never-add-conduct
sentence. Re-sent on that chat's own captured calls (GLM 5.2, reasoning
off, 4 samples each): "Hnnnn~" mutter 4/4 -> normal or pitched 3/4 (4/4 on
the run before); "Haaa... That feels good" mutter 4/4 -> 4/4 not; "More
please." -- written "almost a murmur" by that turn's prose -- still mutter
3/4. The writer, re-run on the same input, now adds reach ("quieter",
"murmured", "low") in 1 of 4 samples against 3 of 4.

**"I think the TARDIS might be irrevocably broken."** Turn 4398 again, three
rolls. The first two ran on the old sheet and never moved the ship; the
second's resolve encoder wrote 1 event for a 5,045-character account (see
below). The third, on the native card, set it off with `transit {in_transit,
closed, destination_room: tardis_console_room, route_room: moonlit_beach}`:
its destination its own console room, "as a placeholder since the actual
Kyoto/Kansai room does not yet exist ... the engine should bind this", and
its route the beach it was leaving -- written at interpret, where the
encoder's own note called it "the place it is leaving from", and carried by
resolve as standing state. Arriving would have opened the console room onto
itself, and mid-vortex its door opened onto the beach. Three fixes:
`apply_transit_dock_edges` drops a destination or route that is one of the
entity's own rooms (a thing cannot travel into its own inside; the arrival
scheduler reads the merged scene, so a timed arrival cannot dock it there
either). The transit part names `destination_room` only for a place the world
already holds outside it -- never its own room, never one still to be built
-- and `route_room` only for a place the world holds that it is in while under
way, never the place it set off from. And `entity_keys_name_held_things`: a
state-only entity written under a key the world does not hold is the thing
its transform's `item` names, when that name is exactly one held thing and
the key is its id copied with at most `ID_COPY_SLIPS` (3) characters wrong or
one of its names -- re-sent on this beat's resolve call, all six transits
written for the TARDIS across twelve samples, on either sheet, were keyed
`75bd6ac12fa14a5d`-style slips of `75bd6ac12fa14e7d`, and the merge filed each
as a new nameless entity while the ship stayed put. (The owner's own 33
encoder calls keyed all 28 entities right.) On the owner's interpret call,
GLM 5.2, reasoning off, 10 samples an arm:

| | old part | shipped |
|---|---|---|
| transit written | 5 | 2 |
| route = the beach it was leaving | 3 | 0 |
| destination = a place that is not the destination | 1 | 0 |
| route = an id nothing holds ("the vortex") | 0 | 1 |

Most shipped samples held off because the page had the ship only beginning
to dematerialise ("has not yet entered transit ... 'first tremors'"), which
leaves the departure to resolve: on the resolve call with the inherited
transit removed, 24 samples across three runs, 11 set the ship off (5 of
them under a slipped id, which the merge would have given a phantom) -- 4
with no destination, 7 naming `new:Kyoto` (see Open), 8 with no route, 2
routing through `new:the Time Vortex corridor toward Kansai` and 1 still
through the beach. Of the other thirteen, eight stopped after the first 3 or
4 of the account's ten or so happenings, before the ship commits (see Open),
and the rest wrote no transit the engine reads, two saying in their notes
that they had. The console room's text
still says "The doors behind stand open to the night beach": minted before
`7959ac5f`, and rerolling does not reach it.

**Open:**
- **An encoder that stops early loses the end of the beat** -- now answered
  by the check and repair pass (`agents/director_repair.py`,
  `prose_contract_repair`: opt-in when built on 2026-09-24, ON by default
  since 2026-09-28; the owner's design: Jev finds the missing events
  and the missing or wrong ledgers, builds a targeted encoder for them with
  the completed ledgers in its context, and orders what comes back).
  Three of the owner's resolve calls encoded 0-2 events of 2,852-5,104
  character accounts (captures 3880, 3890, 3962), and the latest roll of
  turn 4398 (3998) one event of 23 sentences. On eight hand-labeled beats the
  pass covered 50 of 66 missing sentences (counted by the recovered events'
  own text) at a median 4-5 s a beat -- 3998 went from 1 event to 9-10 in 3
  of 3 runs -- and declined every false alarm it was handed; six versions of
  the repair's framing, and of Jev saying what a flagged write has wrong
  (where it belongs: yes; which condition fails: no), are measured there
  too, in `docs/experiments/ENCODER_REPAIR_2026_09_24.md`. The last roll ran
  the encoder at reasoning `medium`, and the repair call uses the same role.
  **Most of the early stop was the grammar** (2026-09-25): the same captured
  payloads re-sent 78 times each way stopped under half their best coverage
  18 times with the enforced `json_schema` and 2 times with no response
  format, and left a declared act with no event 11 times against 0. The
  encoder role now goes without it by a measured default the models panel
  shows and a host can override (`providers.ROLE_DEFAULT_FORMATS`); the
  repair and any rebuild of a broken answer keep it. An act the cast
  declared that no event carries is found by code and made a certain
  repair job (`director_repair.declared_gaps`), and a repair answering one
  job in pieces is no longer cut to its first piece (`merge_answers`; 192 of
  844 recovered events had been dropped that way).
- **Where a vehicle sets off from is never where it arrives -- built, by the
  owner's ruling (2026-09-25):** "the location of departure cannot be the
  location of arrival and that is perfectly fine for vehicle to be contained
  in no room with a perpetual in transit state until the story declares
  otherwise." The repair of 3979 had written the beach as the TARDIS's route
  because the draft's other transit writes did; fresh drafts with no grammar
  still did (3 of 3 samples), one reroll of turn 4398 wrote it as the
  DESTINATION with an ETA of 5 s, and the ship's own position stayed on the
  beach the whole journey. `spatial_transit.settle_departures` now holds it:
  setting off keeps `departed_from` for the journey, a destination or route
  naming it is dropped (its ETA with it), and under way the vehicle stands in
  its route or in no room until a write brings it in. Rerolled live, the
  TARDIS left the beach for no room in 2 of 2.
- **Under way it is somewhere -- the same evening, from three branches of
  that departure.** Chat 154's active roll built `in_the_time_vortex` as the
  ship's route (the prose author had sent it `new:in the time vortex`) and
  held together for the two beats after: in transit, the beach remembered,
  one shut door into the vortex. Chat 156 routed it through `the_open_sea`.
  Chat 157 named no space -- the transit part allowed a route only for a room
  the world already held, and left it out for a journey through "nowhere a
  body could step" -- and its next beat wrote the ship `docked` in no room,
  which erased `departed_from`, so the beat after set it off again with
  nothing remembering the beach; its scanner and power readouts meanwhile
  named a vortex the world did not hold. No room was the floor the ruling
  allowed, and it had been read as the place to stand. The part now says
  setting off names the space it moves through as `route_room` -- the room
  the world holds for it, or `new:<the prose's own words for that space>` --
  and that nothing arrives nowhere; the room author builds a `new:` route as
  it builds any new place. `settle_departures` carries the route through a
  later write that does not name another, as it carries `departed_from`, and
  keeps a vehicle `docked` with no position, destination or route under way.
  A route naming no room is kept for the step that builds it and derives no
  doorway (the rewrite had drawn `{"to": "the vortex"}` from a console room
  whose ship was in no room). In no room remains the floor; code never
  invents the space.
- **A moving room's doorway keeps no passage record** (chats 156 and 157). A
  World Browser edit to the TARDIS's doorway on the beach minted one, and
  `sync_scene_passages` -- after the dock rewrite -- minted the beach edge
  back on every merge: 157's console room had a shut door onto the beach
  while its ship was in no room, 156's opened onto the sea and the beach at
  once. `spatial_transit._release_dock_passages` folds such a record into the
  door it describes (name, material, width, climb -- `_DOORWAY_OWN_FIELDS`,
  which now also keeps a doorway's `offset` along its wall) and drops it, so
  the door carries itself to every place it docks.
- **A body shown on a screen is not minted where it stands.** Rerolling
  turn 4398, the figure the Doctor sees on the scanner was minted and left
  in no room, or recorded only as the scanner's state; code now grants
  `positions` wherever a mint needs one, and two card wordings that a
  device carries a body's image, never the body, changed nothing in 6 rolls
  (`docs/experiments/ENCODER_REPAIR_2026_09_24.md`).
- **Duplicated events are not checked.** Capture 3979 writes the spark, the
  full vibration and the tilt twice each; fresh drafts do it about 3 times in
  213, and the one signal found (an event re-telling part of another) also
  fires on a line spoken inside narration, which is its own event -- so no
  check was built.
- A departure's destination is still usually written `new:<place>` when the
  room agent is on -- 7 of 11 launches above, citing
  `places_authored_elsewhere` over the transit part's "never a place still
  to be built" -- so the room author builds the city as one room before the
  ship lands anywhere in it. The doorway binds and holds; whether the place
  is right is unread.
- A player line the writer still retells as murmured is still usually
  encoded `mutter` (3 of 4), though the encoder is told the player's reach
  is theirs. A structural floor could close it -- a quiet volume that keeps
  the words from nobody present is pitched for its targets -- but it would
  also flatten a deliberate "mutters at him" meant to be half-caught, so it
  is the owner's call.
- One-off sounds are written a quarter as often (4-6% of calls against
  17%). On the one beat read closely (137 idx 48: a stomach's groan, a
  swallow outside the walls) the old sheet wrote both and the native none;
  putting the old core in front of the native chunks brought them back (3
  of 3), and no single sentence of it tried so far does.
- Obligations are written eight times as often; the one read (a demand,
  "Hold onto the frame and don't let go!") was right and the old sheet
  missed it. The rest are unread.
- The encoder sometimes states a write in `notes` that no event carries:
  "the TARDIS entity's state.hatch is set to closed" with no transform
  (153 idx 23 interpret).
- It wrote an entity interior's doorway edge (`closed_door`) despite the
  core's rule; the dock derivation overrides it, so it is harmless.
- **How long a contact lasts is the owner's call.** On any beat that writes
  `contact_ops`, a standing contact not re-added ages: an act (a strike, a
  kiss) is over at once, a hold on the second such beat
  (`spatial_contacts._CONTACT_STALE_BEATS`). The owner: "Some contacts need
  to hold where as some contacts are brief." A hold that lasts until the
  prose ends it would need the encoder to write the ending; the ageing was
  built because the causal Director almost never did (147 adds against 3
  removes in one story). The encoder card states the rule as it stands.
