# The prose contract: an author that writes, one encoder that builds

**Status: EXPERIMENT, 2026-09-22, branch `worktree-jev-prose-director`.** Off
by default. Selected by the setting `director_contract = "prose"`; the causal
ledger contract ([`DESIGN_SPECIALIST_CONTRACT.md`](DESIGN_SPECIALIST_CONTRACT.md))
stays the default and is untouched when the setting is absent.

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
3. **One encoder does every hand's job** (role `director_specialist`, step key
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
| Channel chunks, verbatim | `_dispatch_specialists`' gates, as the predictor of which tools a beat needs |
| Commit, perception, narrator | — |

## Where it lives

- `agents/director_prose.py`: the contract (`run`, `dispatch`, `ledger_from_events`).
- `llm/decisions.py`: the Jev client (`decide`, `OVERRIDE` for tests).
- `llm/prompts.py`: `prose_director_prompt`, `unified_specialist_prompt`, `jev_channel_questions`.
- `llm/schemas.py`: `ProseDirectorOutput`, `UnifiedEvent`, `UnifiedSpecialistOutput`.
- Cards: `prose_contract/*.txt`, `jev_questions/*.txt` (the `ja` pack carries the English text until translated).
- `agents/director.py`: the two call-site branches and `_run_specialists(answer_for=)`.
- `tests/test_prose_contract.py`.

Each stage's record persists at `orchestration.prose_contract`: the prose,
Jev's probability per channel, the selection, encoder timings, any widening,
and the raw events.

## Known gaps

- **Extension specialist families are not absorbed.** Their sheets are not
  built from engine chunks. Under this contract they do not run.
- **The chunks still speak the several-hands dialect** ("request inventory_ops
  in required_channels"). The core reinterprets it. A native rewrite would be
  shorter, but it would fork the chunks between the two contracts.
- **Establish is out of scope.** The opening turn keeps its own Director.
- **Author-side retries** (world-pressure must-tick, player-authority) re-ask
  the causal Director with corrections. Under this contract they read the
  converted rows, which carry the same fields. That path is untested under
  this contract.

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
tokens in 3–11 s. **Set `director_specialist` to `off` under this
contract**, in Settings → reasoning effort. The encoder transcribes a decided
account; the thinking happened in the Director.

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
- `inspect_rooms`: the neighbours' geometry;
- `draft_room`: builds the room in pieces;
- `view_room`: the draft drawn on the engine's own cell grid, north up, with
  what the engine made of every fixture, and collisions shown;
- `check`: the real merge plus `room_layout_lint`, owed rooms, unplaced and
  overlapping fixtures;
- `submit`: refused while the check fails and steps remain.

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

**Open (real turns):**
- A host now feels a body inside it (the contact survives) but hears it only
  by the room-to-room sound field, which an interior's own acoustics can
  close; a rule for sound through the host's own tissue is not built.
- The encoder's debt errors: discharging the player's debts on its behalf
  ("'Let's do it' implicitly answers all three"), and "consolidating" three
  open debts into two new ones against the tool's own rule.
- The Director's flourish -- a lamp flickering on most beats -- minted
  `lamp_3` beside `lamp` and `lamp_2` rather than reuse a record.
- A player's name reached Vexara's composed view on every turn of chat 120,
  under both contracts; the tripwire repaired it each time. The composer path
  that admits it is not traced.
- Replay divergence is a property of the method, not a finding: inputs
  written for the original timeline do not answer questions the replayed
  characters ask, and the two lanes that diverged (126, 122) read as
  characters insisting on a precondition.
