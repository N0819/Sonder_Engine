# Conversation threads: people in a room talking to each other

Status: steps 1-2 being built (2026-10-07); steps 3-4 designed, not built.

## 0. The ask

The owner, 2026-10-07, after a played story showed the charter's people
chiming into the protagonist's conversation on almost every beat:

> "Charter may be a little overly chatty. which is funny because it started
> off with a stubborn refusal to talk remedied through painful development."

> "I don't want them to seem lifeless and spontaneous talking can happen but it
> shouldn't be the norm, talking to eachother though could be interesting" --
> "but even that I don't want overdone."

> "lets say you ask a charter npc to do something and they imediatley start
> talking to their peers to get the task done so an actualy conversation runs
> for as long as you are in that room. Or of course bar talk/fight etc etc,
> maybe the story planner could initiate some of these if you're in a
> populated room long enough and you can choose to engage with it or not."

The first half landed as a cap (`background.CHARTER_UNADDRESSED_VOICES`, one
unaddressed voice a beat; anybody addressed still answers). This note is the
second half: talk BETWEEN the room's people, as a thing that lasts.

## 1. What exists, and why none of it is this

- **Charter figures** (`background.declare_charter_figures`) are asked at once,
  blind to each other, and the card forbids one referencing another, so they
  cannot form a reply chain. That is deliberate (one line, one answerer;
  words said once) and stays: it is the right shape for bodies REACTING.
- **Background reactors** (`background_react`) are stateless, one beat each.
- **A service debt** (`pending_act`, from a figure's typed `still_owes`) makes
  one figure re-asked each beat until `hands_over` lands -- one person's
  errand, never talk with peers.
- **Ambient chatter** (`world/charter_chatter.py`) surfaces the charter's real
  off-screen social acts as a murmur and at most one overheard triple ("asked
  X about Y") -- grounded, but never words, and rare (one "scattered talk" in
  eight beats of scratch story 166).
- **The scene manager** (`scene_life: ambient|full`, off by default) voices a
  whole room in one call; how often a room talks is then the model's choice,
  and a model asked whether a person speaks says yes ~90% of the time
  (measured 2026-10-07: 13 of 15 asked figures spoke in story 166).

## 2. The primitive

A **thread** is a conversation among the people in one room that persists
across beats:

| field | what |
|---|---|
| `room` | where it is held |
| `participants` | two to four bodies present: charter people, presences |
| `purpose` | what it is for: a task to get done, a matter, a quarrel |
| `origin` | `delegation` (a request), `charter` (the town's own act), `room` (the Writers' Room) |
| `to` | who the purpose serves, when someone does (the asker) |
| `exchanges` | how many have been voiced |
| `last` | the last exchange's lines, so the next follows on |
| `status` | `open` / `done` |

Each beat while someone who can hear it is in the room, the thread advances
by ONE exchange -- at most `THREAD_LINES_PER_EXCHANGE` lines among its
participants -- voiced by ONE call, so they answer each other. It ends when
its purpose is done (the call says so; for a task, `hands_over` lands), when
it reaches `THREAD_MAX_EXCHANGES`, or when it has gone `THREAD_IDLE_BEATS`
unvoiced (everyone who could hear it left).

## 3. The firewall in a group call

One call reads several people at once, which is the one way this could leak
(BACKGROUND_LIFE_DESIGN §3.10's tradeoff). The thread call is the `ambient`
level of that design: it receives only what is COMMON to its participants --
the place, the room's common knowledge, what was said and done audibly in the
room this beat, the thread's own last exchange, and per participant only what
anyone standing there could see or would know of a coworker (name or label,
look, post). No participant's private news, condition or acquaintances enter
it, so one cannot voice another's knowledge; a body with something private to
say says it through its own individual voice.

## 4. How it reaches the page

The exchange becomes ordinary figure declarations (one per participant: its
lines and acts, in order), resolved by the Director, written by the encoder,
delivered by perception through the ordinary hearing rules (whole, fragment,
or nothing by distance and walls), and filed in memory for every mind present.
Nothing new crosses: a thread line is a line said in a room.

The player engages by addressing a participant: that body is then answered
for individually that beat (the existing addressed path), and the thread
resumes after. Ignoring it is free.

It does not count against the unaddressed-voice cap: that cap is for people
talking AT the protagonist; a thread is people talking to each other.

## 5. Where threads start

1. **Delegation** (step 2). A figure that answers a request with an unfinished
   service (`still_owes`) while a peer of its own institution stands in the
   room opens a thread with that peer, its purpose the service and its `to`
   the asker. "Ned, the book's in the back -- go on." Closes on `hands_over`.
2. **The charter's own acts** (step 3, not built). An act the charter's
   simulation runs in a room someone is in (an ask, a quarrel) opens a thread
   on its subject instead of surfacing as a bare triple.
3. **The Writers' Room** (step 4, not built). After someone lingers in a
   populated room, the Room may seed a scene: the matter, the people by post,
   how heated. Its call what fits the story; the player's whether to engage.

## 6. The numbers (the owner's to set)

| constant | value | what |
|---|---|---|
| `THREADS_PER_ROOM` | 1 | open threads in one room at a time |
| `THREAD_LINES_PER_EXCHANGE` | 3 | lines one beat's exchange may hold |
| `THREAD_MAX_EXCHANGES` | 6 | a thread nothing ends sooner ends here |
| `THREAD_IDLE_BEATS` | 2 | unvoiced this long (nobody to hear), it closes |
| `THREAD_PARTICIPANTS_MAX` | 3 | the delegating body plus two peers |
