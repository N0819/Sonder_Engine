# Background presentation: ambient chatter, the crowds bridge, and demand-driven voice

**Status: design only. Nothing below is built.** Written 2026-08-27 on the
`social-physics` branch, refining the owner's three-tier design in
`docs/UNBUILT.md` §1.99e (which depends on §1.99d's person/institution split).
The three parts are one substrate and two presentation layers: Charter is
every unregistered person; the voice tier renders whoever is actually in an
exchange; the crowd carries the rest. Ambient chatter is the sound the third
tier makes.

Everything measured here was measured on this branch on 2026-08-27; the
scripts are throwaway and the protocol for each number is stated inline so it
can be re-taken.

---

## 0. What was measured before designing

**Acts per window, `twin_towns(40)`, 180 windows of 4h (30 simulated days),
seeds 0..179**, via `charter_run.step` directly:

| quantity | min | median | p90 | max |
|---|---|---|---|---|
| acts per window, whole charter | 4 | 19 | 22 | 25 |
| acts per window, busiest single place | 2 | **4** | 6 | 8 |

- Bodies co-present at the busiest place: median 5.
- Act mix: **95.2% `ask`** (3,126), 4.8% `greet` (157), zero `tell`/`tend`/
  `accuse`/`reconcile` in a healthy run.
- Cost: 56.4 ms per window for the whole charter, model-free.

Two corrections to the brief fall straight out:

1. **"Eighteen lines per beat" is a whole-institution number, not a room
   number.** Perception is room-scoped (`agents/common.py:1489`,
   `crowds_for_room`'s own docstring), so the narrator's observer never sees
   the 18; the room they stand in carries a median of 4 and a p90 of 6. The
   design problem is still real — four verbatim lines per beat is still
   wrong — but it is a factor-of-4 problem, not a factor-of-18 one.
2. **The lines are monotonous by construction.** With the current affordance
   mix nearly every act is `{actor} asked {other} about {subject}`
   (`world/charter_practice.py:515`). Rendering several verbatim would not
   read as a living room; it would read as the same sentence with the names
   rotated. Summarisation is forced by the material, not only by style.

**Payload scaling of the one batched voice call** (`scene_life`,
`agents/background.py:640`): the system prompt is 5,332 chars (~1.3k tokens);
a representative cast entry (the field set at `agents/background.py:657-668`,
blurb strings at observed lengths) costs ~310 tokens. Measured on synthetic
but shape-faithful payloads: 4 cast → ~1.1k payload tokens, 8 → ~1.75k,
16 → ~3.0k. Input grows mildly and linearly; the term nobody has measured is
**output** tokens and wall-clock, which need a live model (protocol in §C4).

**Timing of the substrate.** Charter advances out-of-band after commit
(`persist/commit.py:548` → `charter_runtime.schedule_charter_ticks`,
`world/charter_runtime.py:1748`) on the story clock's `elapsed_seconds`
(`world/offscreen.py:491`, "how long they have been on their own"). A slow
conversational scene advances story time by minutes per beat, so fresh acts
arrive every few beats at best, and the acts readable at perception time are
the last landed window's. Consequence for everything in Part A: chatter is a
*standing texture that refreshes occasionally*, never a per-beat feed, and
any reader of it must tolerate a one-beat-or-more lag and must dedupe.

---

## Part A — Ambient chatter

### A1. How prose fiction actually renders a crowded room

Read for this note, 2026-08-27. Four principles recur across craft advice,
the modernist party scene, and — the closest analogy to our situation — sound
design for a single-channel medium.

1. **Attention is the filter, and the point of view does the filtering.**
   Patricia C. Wrede's crowd-scene advice is the plainest statement:
   *"staying solidly behind the POV character's eyes helps enormously"* — if
   five people are yelling at once and the POV cannot make out any of them,
   the author writes none of them. Dialogue runs in "short, three-to-five-line
   exchanges limited to two or three people"; a mob is broken into
   two-or-three-person clusters that "take brief turns on center stage"
   (<https://pcwrede.com/pcw-wp/crowd-scenes/>; same doctrine at
   <https://www.writersdigest.com/writing-articles/crowd-control>). The
   engine already owns this filter: it is the perception layer.

2. **Figure and ground: at most one thing is foregrounded at a time.**
   Fitzgerald's party scenes anonymise the mass — people become labels and
   hazy actions, "voices rise and collide", and almost nothing the crowd says
   is attributed or even quoted (analyses at
   <https://medium.com/@baileyayork/narratological-reflections-on-the-great-gatsby-part-i-fe06e8903616>,
   <https://www.enotes.com/topics/great-gatsby/questions/literary-devices-and-elements-in-the-great-gatsby-3134554>).
   Woolf's street and party scenes get their crowd effect from fragmentation
   — snatches of perspective, not transcripts (Grisot, Conklin & Sotirova
   2020, <https://journals.sagepub.com/doi/10.1177/0963947020924202>). The
   crowd is ground; a fragment is promoted to figure only when the POV's
   attention snags on it, and then it is *one* fragment.

3. **Synecdoche: one chosen detail stands for the whole.** "A sea of faces";
   "fifty pairs of eyes" — the part for the whole is the standard figure for
   mass presence, and one well-chosen instance beats a paragraph of
   enumeration (<https://www.grammarly.com/blog/synecdoche/>,
   <https://writingexplained.org/grammar-dictionary/synecdoche>; the Dickens
   scholarship is Gomel, *The Body of Parts*,
   <https://www.jstor.org/stable/30225439>). `crowds.describe`
   (`world/crowds.py:562`) is already a synecdoche generator: band +
   composition + fit-to-room, no enumeration.

4. **The walla rule: background speech is deliberately unintelligible.**
   Film and radio call the crowd murmur *walla*, and radio walla — the
   single-channel case, which prose also is — is kept indistinct **on
   purpose**: "you don't want a walla quip or phrase to break above the
   murmur or into a pause by the foreground characters … that could divert
   the listener and step on an important line of dialogue"
   (<https://ruyasonic.com/sfx-walla.htm>; overview at
   <https://en.wikipedia.org/wiki/Walla>). Prose has exactly one channel:
   **anything rendered verbatim IS foreground.** There is no way to print a
   sentence quietly.

The synthesis, stated in engine vocabulary: *the room's talk reaches an
observer as ground — a summarised, anonymous murmur — plus at most one
figure: a single overheard fragment, admitted only when the deterministic
layer judges the observer's attention would snag on it. More people means
more murmur and, past a point, fewer intelligible fragments, not more.*

### A2. What the engine hands the narrator

Two objects per observer per room per beat, both delivered through the
perception layer (§A3), both derived, neither stored.

**A2a. The murmur: one clause of ground.** A HUM band derived from the count
of last-window acts whose actor stands in the observer's room (actor's
`place`, the same presence test `charter_news.witness` uses,
`world/charter_news.py:272`), graded against the crowd band already present:
silent / scattered talk / a steady hum / a din nothing carries over. It is a
band for the same reason the crowd's count is (`world/crowds.py`'s module
note): nobody writes "eleven conversations", and two sources disagreeing
about a number is a dispute nobody can resolve. It rides the existing crowd
description — one more clause in `describe`/`crowds_for_room`'s `what`, or a
sibling field beside `talk` — never a list of lines. Zero model calls; the
whole cost is a filter over a list the registry already holds
(`after_charter["acts"]`, `world/charter_run.py:1177`).

The hum's inputs must be the acts *and* the band together: a handful
produces scattered talk however busy the window was, and a throng produces a
hum even in a window that landed no acts (the acts sample the population;
they do not exhaust it). Exact thresholds are vocabulary, not tuning —
choose them once so the words keep their plain meanings, the same way
`BANDS` did.

**A2b. The fragment: at most ONE, structured, not the template line.** The
selector is deterministic and runs over the same room-filtered act list:

- **Eligibility** (any one): the act's `other` or `subject` names a body the
  observer's beat is entangled with — a present registered character, the
  player, or an emerged presence (dramatic irony: the one fragment worth
  hearing is the crowd talking about *you*); or the act's kind is one
  `_ACT_EVENTS` already deems relationship-changing (`world/charter_run.py:95`
  — `tend`, `accuse`, `reconcile`: the room already witnesses these as
  events, so surfacing them is rendering a fact the observer's mind was
  going to hold anyway); or, failing both, an ordinary act may surface on a
  seeded low-rate draw so a long quiet scene still occasionally yields an
  overheard nothing — texture, not information.
- **At most one per room per beat, and the same act never twice.** Dedupe on
  the act's identity (actor, act, other, window), the same discipline as
  composer `dedupe_key`s (`agents/composer.py:1567`).
- **What crosses is the triple, not the sentence.** The engine holds no
  sentence content — `line` is a skeleton
  (`{actor} asked {other} about {subject}`,
  `world/charter_practice.py:515`) — so hand the narrator structured fields
  `{speaker_label, act, other_label, subject_label}` and let it write the
  fragment. Never put the template line itself in a prompt: a literal string
  in a payload gets restated (the chat-78 lesson `scene_ledger`'s docstring
  records at `world/charter_log.py:226`; the auto-memory note "literal
  guards fail when models rewrite" is the same failure from the other side).
  The information budget is the triple *by construction*: what was said
  aloud in the room is who-asked-whom-about-whom, and that is all the engine
  itself knows, so the narrator cannot be handed more.

**A2c. Attribution follows recognition.** The naming pass is
`charter_identity.display_name` (`world/charter_identity.py:637`) — but only
for a participant the observer can identify: an emerged body, a body with a
live presence record the observer has met, or one whose post is visible in
the room (a role noun from `posts`, which is engine vocabulary). Everyone
else is anonymous, in `crowd_voice`'s register (`world/crowds.py:603` — "NEVER
a name": naming an unmet stranger invents a person nobody interacted with,
the exact falsifier DESIGN_CROWDS §7 lists). Note the asymmetry that makes
rumour work: the fragment's *subject* may be named even when the observer
does not know them — overhearing a stranger's name is how a name first
reaches you — because the name was said aloud; it is the *speaker* who may
not be identified beyond what a bystander perceives.

**A2d. Degradation with crowding is an inversion.** As density rises,
intelligibility falls:

| density (`world/crowds.py:140`) | murmur | fragments |
|---|---|---|
| `loose` | scattered talk | up to one, ordinary eligibility |
| `packed` | steady hum | up to one, but only high-salience eligibility (entanglement or `_ACT_EVENTS` kinds) |
| `crush` | din | none — the roar is the whole percept |

The argument is the walla rule plus the engine's own physics: `crush` is
already a `membrane` you cannot see across (`world/crowds.py:163`), and a
press you cannot see across is one you cannot pick a single voice out of.
More crowd = more ground = less figure. Eighteen lines was wrong in kind,
not just in count; the correct number is **zero or one**.

### A3. The firewall route: structured observations, not prose texture

The owner's lean in §1.99e is confirmed, with the argument:

**Ambient lines reach the narrator as structured observations through the
perception layer** — concretely, as fields on the existing crowd view
(`crowds_for_room`, `agents/common.py:1489`), which perception already
delivers per-observer and room-scoped (`agents/perception.py:1764` and
siblings) and the composer already folds into `ambient` percepts
(`room_content_percepts`, `agents/composer.py:1537`). Three reasons:

1. **The admission decision is already made in the right place.** Every
   `crowds_for_room` caller passes the observer's own room; the composer's
   docstring says outright that the world seams "have ALREADY decided what a
   bystander in that room takes in" and nothing downstream re-decides it. A
   fragment delivered here is inside the information budget by the same
   argument as a courier's visible bearing or a posted notice.
2. **The re-derivation property holds automatically.** Structured
   observations are re-derived from the rendered view
   (`composer.observations_from_render`), so a character standing in the
   room receives the fragment legitimately, through the same door the player
   did — no second representation that could expand the budget. A
   narrator-side "texture" channel would be exactly such a second
   representation: prose handed around the budget, unauditable, and the
   zero-content assertion (a crowd seen across a doorway is a shape and a
   sound) would have no enforcement point.
3. **The witness rule and the perception route are the same rule at two
   tiers, not two rules.** `charter_news.witness` admits by presence — the
   body stood where it happened. The fragment selector admits by presence —
   the act's actor stands in the observer's room. Routing "through
   `witness` rather than around it" is satisfied in substance: the observer
   is treated exactly as one more body in the room, and what crosses is what
   a co-present charter mind would have been eligible to hold.

**What deliberately does NOT change: `_ACT_EVENTS` stays as it is.** The
tempting symmetric move — add `ask`/`tell`/`greet` to `WITNESSABLE`
(`world/charter_news.py:40`) so bystander charter minds also overhear
ordinary chat — is refused. The membership rule there is principled (*an act
is an event iff it changes what two people are to each other*,
`world/charter_run.py:82-100`), and the cost is real: at the measured median
of 19 acts/window against ~5 co-present bodies, witnessing ordinary chat
deposits on the order of a hundred claims per window into heads whose claim
caps and decay would then churn on noise. Talk of the Town's salience lesson
(RESEARCH.md §1.7.2 — one number drives observation, propagation and
deterioration together) says ordinary chat sits below observation salience.
Offscreen participants already learn through `hear` inside the affordance
effect; onscreen bystanders learn through the rendered fragment. Nobody else
needs to.

**Staleness is admitted, not hidden.** The fragment renders acts from the
last landed window (§0), which may be minutes of story time old. That is the
same one-window lag `charter_run` already defends for judgment ("nobody
revises their view of a person in the same instant they watch them act",
`world/charter_run.py:911-916`), and for a murmur it is honest: overheard
talk in a room *is* ongoing, not synchronised to the player's beats.

---

## Part B — The crowds bridge

### B1. The principle: a charter crowd is a read-time projection

`world/crowds.py` was written after the `wearing`/`state`/`regions` scar and
says so; its stored object is Director-authored people who exist *only* as a
band. Charter bodies are the opposite: fully simulated people who need a
cheaper *presentation*. So the bridge is not "put charter people into the
crowds ledger" — that would store a band, a composition and a membership that
drift the moment `charter_move.errands` walks a body elsewhere, i.e. the
exact second-source-of-truth the module exists to refuse.

**A charter crowd is derived at read time and never persisted.** Two species
share one view shape:

- **Authored crowd** — stored in the `crowds` world key, as today. People who
  are *only* a band. Unchanged.
- **Charter crowd** — computed inside `crowds_for_room` from the registry
  snapshot: the charter bodies whose `place` is the observer's room, minus
  every body presented individually this beat (bound bodies —
  `state["bindings"]`; bodies with a live overlay presence record —
  `with_charter_presences`, `persist/commit_background.py:828`; figures).
  Nothing is written anywhere.

Derived fields, each from data the charter already owns:

- **uid**: minted deterministically from `(chat_id, charter_key, place)` —
  stable across beats without storage, in `crowd_uid`'s spirit
  (`world/crowds.py:236`): from what the crowd IS, never a display name.
- **band**: a pure count→band function over the membership count. This is
  the one place an integer meets the band vocabulary, and it points the safe
  direction: integer → word is a projection; word → integer (the arithmetic
  the module refuses) still never happens. Thresholds are vocabulary — set
  once to match the words' plain meanings, like `BANDS` itself.
- **composition** (≤120 chars): from what the members ARE — the dominant
  post/role nouns among them (`posts` keys via the watch bill, then the
  charter's naming profile's collective noun as fallback). Engine
  vocabulary by construction: posts are authored per charter, so the string
  is genre-correct without this module knowing any genre.
- **mood** (≤24 chars): from the members' aggregate strain
  (`charter_feel.strain_of`, `world/charter_feel.py:394`), banded. Derived,
  so a place whose people are worn reads worn without anyone authoring it.
- **heading**: none. Charter bodies move individually on their own errands;
  a derived crowd has no collective current unless the institution gives it
  one (see B4).

### B2. When a place becomes a crowd

Not at a headcount — at the *presentation boundary*: a charter body is ground
(in the crowd) exactly when nothing this beat presents it individually. The
threshold question is then only the degenerate low end: two unvoiced bodies
are not "a crowd", they are two figures the existing background ledger can
carry. Propose: below the floor of the smallest band, members present as
individual ambient figures through the existing overlay path; at or above
it, as the derived crowd. The floor's exact value is a taste constant;
DESIGN_CROWDS §7's falsifier ("bands read as vague rather than atmospheric")
is the measurement that would move it, read from play, not picked here.

### B3. `emerge` and `absorb` against Charter membership

**Emerge = the body acquires an individual presentation.** For a charter
crowd the op names a charter body ref (`(charter_key, body_key)`, the
addressing `_body_refs` already resolves, `world/charter_runtime.py:2179`) —
or omits it and lets the engine pick, which is where the week's new stores
earn their place: the selector ranks members by entanglement with whoever is
present — a tie, a grievance (`grievance_against`,
`world/charter_practice.py:419`), a mark, `served_beside` history with a
present body — exactly the `_between` digest the affordances already weight
utility on (`world/charter_practice.py:331`). The person who steps out of
the crowd is the one with a reason to. Mechanically, emergence is the
existing overlay: `with_charter_presences` resolves the ref into the
presence ledger, identity-carefully, and the derived crowd excludes them
from membership on the next read — no `emerged` list to store, because the
presence record IS the record. (This also repairs a bend in the module's own
rule: the stored `emerged` list keys people by display name,
`world/crowds.py:446-484`, in a module whose docstring says uid never a
display name. The charter path keys by body ref and needs no list.)

**Two rules from DESIGN_CROWDS survive; one is superseded.**

- *"A crowd may never emerge a named character"* survives: charter bodies
  are unregistered by definition (bound bodies are excluded from membership
  above), so the crowd still produces only people the story's cast does not
  contain — but they are no longer strangers to the WORLD, only to the
  record.
- *The one-way rule for anyone who speaks* survives unchanged, and its test
  ("does anything durable now name them", `world/crowds.py:486`) is still
  the right one — a charter body that spoke has a presence record and a
  `dialogue_log` history and cannot be deleted back into the mass.
- **Superseded: DESIGN_CROWDS §3a's "an emergence may not be re-met."** For
  a charter crowd the opposite is the entire point: the body persists in
  Charter with its ties, marks and diary, so the person who stepped out
  last visit IS there next visit. §3a's fixture/emergence table should gain
  an amendment row saying the distinction collapses for charter-backed
  crowds — a fixture is simply a charter body with a post here. Register
  the residual in `UNBUILT.md` when this lands (it is the only status list).

**Absorb = the body loses its individual presentation, and nothing else.**
The answer to "what happens to a body's simulation while it is absorbed" is
**nothing, because it never had a separate simulation to lose**: Charter
simulates every unbound body every window whether or not anyone is looking
(that is §1.99d's whole argument). Crowd membership is a lens; it must never
touch `bodies`, `minds`, `needs` or any of the fifteen person stores.
Absorption for a never-spoke body is just the overlay record not persisting
(which `with_charter_presences`'s docstring already promises: noticing a
worker must not write a second identity store). This is also why the bridge
is cheap: there is no state transition to get wrong in either direction.

### B4. Ops on a derived crowd, and `MAX_CROWDS`

**A Director op that would rewrite charter population is refused.** `move`,
`split`, `disperse` and `set` on a charter crowd would make `crowd_ops` a
second writer on where charter bodies stand — the scar again. `apply_ops`
(`world/crowds.py:284`) already refuses uids it did not mint; a charter
crowd's uid is recognisable by construction, and the only op it accepts is
`emerge`. If the Director needs the mass itself to surge or scatter, that is
an institution-level fact and goes through Charter's own authored-conduct
seams (`enact`'s `conduct`, interventions via `apply_due`) — named here as
the seam, deliberately not designed here.

**`MAX_CROWDS = 8` holds, and charter crowds do not count against it.** The
constant's own comment says what it is: a coherence limit on the Director
*populating rooms nobody is standing in* (`world/crowds.py:272`). A derived
crowd is the opposite case — people who verifiably ARE standing there — and
it occupies no ledger row. Its natural bound is structural: at most one per
charter per room, read only for rooms an observer is in, and `place_view`
already caps co-located charters at 3 (`world/charter_runtime.py:1806`,
`ledgers[:3]`). So the view yields at most ~3 derived crowds per room plus
whatever authored crowds stand there, and the 8-cap keeps doing its one job
on the authored ledger.

---

## Part C — Demand-driven voice handoff

### C1. The trigger vocabulary

Per the owner's addition (2026-08-27): **non-charter characters are treated
as presences like the player for interaction with Charter.** So define the
trigger set over *authored minds* — the player, registered cast, extra
players — not the player alone. A charter body qualifies for voicing this
beat when any of:

1. **It was addressed.** An authored mind's overt declaration names it
   (`overt_declaration` + name/role matching,
   `persist/commit_background.py:874` — the gate that already exists and
   already strips concealed elements), or a roster speaker aimed a
   `dialogue_log` line at it (`_character_address_of`,
   `persist/commit_background.py:944`, which already covers characters
   addressing extras and already fails closed on concealment).
2. **It owes a reply** that has not expired (`_valid_pending_reply`,
   `persist/commit_background.py:986`).
3. **It acted toward an authored mind last beat** — a fired background
   reaction aimed at one, or a charter act whose `other` resolves to a bound
   body or scene figure (`presence_view` already builds exactly this
   aperture per body, `world/charter_runtime.py:2057`, action instances
   included).
4. **It emerged this beat** (Part B's selector or an explicit `emerge` op) —
   emergence is a demand signal by definition: someone wanted this person.

Explicitly NOT triggers: co-presence, salience, recency. Those are the
current `managed_presences` sort (`agents/background.py:503`), and they are
what makes the budget load-bearing.

### C2. The docstring tension, resolved by the tier split

`managed_presences`'s docstring rejects salience gating because it "makes
extras feel reactive rather than alive" — the manager is handed the populace
so the room can act unprompted. Demand-driven voicing looks like a return to
the reactive gate. It is not, because the *alive* half moves tiers: Part A's
murmur and fragments and Part B's derived crowd now carry "the room is doing
things unprompted" for zero model calls, and Charter's own acts are the
unprompted life (median 4 per room-window, measured, model-free). The voice
call stops being how the room seems alive and becomes what it should have
been: how a person in it holds up their end of an exchange. That is why
demand-driven does not re-mint the `flow.reactors` defect: the two questions
— "does the room live" and "who speaks" — get two different mechanisms
instead of one vocabulary answering both.

### C3. Budget, overflow, and tenure

- **`max_managed` becomes a ceiling, not a target.** The demand set is
  usually 0–2; the ceiling only matters on overflow. Its default can stay
  where it is until §C4's measurement says otherwise — the point of
  demand-driven is that the constant stops being load-bearing
  (`docs/UNBUILT.md` §1.99e says exactly this).
- **Overflow order**: addressed > owed reply > acted-toward > emerged, ties
  broken by the B3 entanglement digest, then stably. **An addressee is never
  silently dropped** — a player's (or character's) named counterpart failing
  to answer is the one visible failure mode. If addressees *alone* exceed
  the ceiling, the address was to a crowd, and the legible degradation is to
  answer as one: the derived crowd is the chorus presence
  (`story/scene.py:2227`'s "one chorus presence" intent), and the beat says
  so rather than voicing eight people badly.
- **Tenure: none, but conversations persist.** A body voiced last beat
  re-qualifies only through the triggers — and an open exchange keeps
  triggering (an owed reply is trigger 2; being answered is trigger 1). A
  body neither addressed nor addressing for K consecutive beats returns to
  ground with no ceremony and no loss: its charter simulation never paused
  (B3), so re-voicing later is cheap and consistent. K is the beat-tier
  analogue of `IDLE_CLOSE_HOURS` (`world/charter_practice.py:108`); set it
  from persisted traces (`persist/pipeline_trace.py`) by measuring how often
  a player re-engages a presence after exactly one, two, three beats of
  inattention — pick K covering ~90% of resumptions rather than guessing.

### C4. Latency and the missing measurement

**Deciding late costs nothing new.** Every trigger input exists by the time
the background stage runs (after `director_resolve` in the normal-turn plan),
which is where `scene_life` already runs; the demand filter is deterministic
and O(presences). No new stage, no new model call, no reordering.

**What was measured**: input scales ~310 tokens per cast entry
(4 → 16 cast ≈ 1.1k → 3.0k payload tokens on a ~1.3k-token prompt, §0). So
input-side, 16 presences is under 2× the total tokens of 4 — mild.

**What is NOT measured and matters more**: wall-clock and output tokens,
because output scales with how many bodies the model chooses to voice, and
output is the dominant latency term (the auto-memory note on sub-minute
turns puts the character call at ~22.5s, never cached — the manager call is
in the same family). Protocol to settle it, runnable in an evening: one
seeded scene, `max_managed` forced to 4 / 8 / 16 with the demand filter off,
10 calls each against the live `agent_models` (read live — they change),
report median wall-clock and output tokens. Prediction to falsify: wall-clock
grows with cast mostly through output, in which case demand-driven voicing —
which shrinks the *handed* cast to the demand set — caps the cost directly
and `max_managed`'s default is nearly irrelevant. If wall-clock instead grows
with input, the ceiling stays load-bearing and should be set from the curve.

---

## What would falsify this design

- **Fragments read as spam or are never noticed** — the eligibility floor or
  the seeded rate is wrong; both are one constant, and A2b names the
  measurement (play, not tuning tables).
- **The murmur gets restated as content** — the narrator turns "a steady
  hum" into invented dialogue lines. That is the payload-restatement class;
  the fix is prompt-side contract plus keeping the triple structural, and if
  it cannot be held, fragments must drop to `_ACT_EVENTS` kinds only.
- **Derived crowds drift from the registry** — any reproduction of a stale
  band or composition proves something got stored; the fix is deletion of
  the storage, not reconciliation.
- **Demand-driven voicing makes rooms feel dead** — C2's claim that the
  chatter/crowd tiers carry "alive" is wrong, and the populace hand-off in
  `managed_presences` was doing real work. Measurable: unprompted background
  acts rendered per beat before and after.
- **Addressees go unanswered** — the overflow rule failed; this is the one
  hard guarantee in Part C.

## Open questions, honestly

1. **The hum's derivation when no acts have landed** (new chat, charter
   never ticked): band-only fallback is proposed but the seam where the
   first window lands relative to the opening turn needs checking against
   `presim_registry` (`world/charter_runtime.py:760`).
2. **Fragment frequency.** "Seeded low-rate draw" is a placeholder; the
   right rate is a play question. A2b says what to watch, not the number.
3. **The count→band thresholds and the crowd floor** (B1, B2). Vocabulary
   choices; proposed to set once, but the falsifier for the floor needs a
   real playthrough (`tools/fire_rates.py` is where DESIGN_CROWDS said to
   read emergence rates, still unrun).
4. **Whether `_ACT_EVENTS` should ever grow a speech kind.** Refused here on
   measured cost and the membership rule, but if play shows bystanders
   plausibly *should* remember overheard accusations-adjacent chat (asks
   about a disgraced name, say), the cheap door is widening the fragment's
   eligibility, not the event set — that boundary might be wrong.
5. **Institution-level crowd motion** (B4): moving the mass through Charter
   conduct/interventions is named as the seam and not designed. It is the
   `heading`/`drift` half of the bridge and someone will want it.
6. **The manager-call measurement** (C4) is specified, not taken: it needs a
   live model and an evening. Until it is taken, every statement about
   `max_managed`'s default is provisional.
7. **Ordering against §1.99d.** The person/institution split moves the
   fifteen person stores this design reads (`ties`, `marks`,
   `served_beside`, `experiences`). Everything here reads them through
   existing seams (`_between`, `scene_ledger`, `presence_view`,
   `with_charter_presences`), so the split should pass under it — but B3's
   body refs are `(charter_key, body_key)` today and become registry-level
   ids after the split. Build after the split, or keep refs behind
   `_body_refs` so only one resolver changes.
