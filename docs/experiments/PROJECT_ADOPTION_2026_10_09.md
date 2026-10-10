# Lasting wants under the bare contract: what took the project slots, and what never reached them (2026-10-09)

**Question.** The owner's ask of 2026-10-09 ("Recommendations for immersion and
realism?"), recommendation 2: characters' wants that last. The last count
(2026-09-19, the full card) was 0 of 18 characters ever holding a project.
Since 2026-09-27 the bare card is the only character contract, and a project
is adopted only through the notebook: an entry written with an `until`, read
back by the decision model as a `commitment`, and passed by
`affect.adoption_refusal`. What does the tier hold now, and what keeps lasting
wants out of it?

**Answer.** The tier is no longer empty -- it is full of the wrong things.
Every one of the fifteen distinct adoptions the bare contract made in play was
an errand or a reading of someone ("Ringer or workman -- find out which before
Coyle asks him anything", satisfied three beats later), and none was a
character's lasting aim. Since the bare card replaced the full card, **the
distinction the tier exists for is stated in no text a model reads.** The
read-back's `commitment` ("something you mean to bring about yourself, and will
keep at until it is done") is true of an errand, and the review section v4 made
reachable for a mind with nothing standing spoke only of "the work you have
taken on". Meanwhile the lasting aims characters did voice went to `changes`
lines, which the read-back can only file as intentions -- the tier that dies
with its tactic.

The line is the owner's, in `CLAUDE.md`'s psychology section: projects carry
"the ordinary long intentions a life has -- take the injured one to a doctor,
go home, go to the bar", durable but not eternal, able to name a place, immune
to being satisfied by one instance, decayed by a barren stretch or abandoned
with the tactic that served it. A journey, the injured carried to a doctor and
a single-session arc that runs until its end comes about are projects; a
one-instance errand stays an intention.

Fixed: the read-back asks every entry written with an end whether it ends on
arriving where it leads -- a place, or the last of its stages -- or is one
thing to do or find out, done in one go (`character_jev.commitment_lasts`); an
errand is filed as an intention, and an aim the intention ledger has no room
for is kept as a reminder in the mind's own words rather than dropped; the
review beat invites a mind with a free slot to take up what it means to see
through (`character_bare.project_take_up`); the card's notebook and `changes`
sentences name the class; an intention going dormant is a boundary; and the
drift marker the bare payload had dropped is back on the notebook, with the
design's escalation. Measured on 49 phrasings of everyday journeys -- the
owner's three, going home, to the bar and the injured to a doctor, fourteen
ways each, and seven others -- each written into a captured beat of its
speaker: the line keeps 47 of them, where the wording it replaced kept 35; it
reads 2 of 36 written errands and 2 of 28 stored ones as ways. **End to end the circularity gate decides the journeys**: a journey's
end names where it goes, the gate reads that as a task restating itself, and
only 17 of the 49 become projects (13 before) -- whether the gate should hold
for a way to a place is the owner's question. Nothing has yet been seen
forming in a faithful live replay (below).

## What the stores hold

Read-only over the scratch play database (142 chats, 4,350 turns; the owner's
`engine.db` holds the same history up to chat 163 and nothing later) and the
live scratch database (Kirinoura and the lookout story). Active variants only.

| | full card (to 2026-09-26) | bare card (from 2026-09-27) |
|---|---|---|
| `project_ops` adopt ops filed | 26 (most are branch copies of one story) | 9 (15 distinct across all variants) |
| refused as circular | 17 (4 distinct: the containment work and two single-session rejuvenation arcs, all ways to an end by the owner's line, and a single feed) | 0 |
| refused as restating a held project | 4 | 0 |
| refused as full / with no criterion | 0 / 0 | 0 / 0 |
| established (served 3 beats over 12) | 4 (one project, four branch copies) | 0 |
| lapsed on probation | 0 | 0 |
| ended by the character | 4 displaced | 3 satisfied, 1 displaced (chat 166, after 1-7 beats) |

The fifteen bare-era adoptions, by story: Sarah Moon (chats 160/161) "Three
minutes of closed steel box ... Do not spend it on the alarm"; Hester Gale
(chat 165) seven -- "Get the name and the boat", "Find out whether Abel's in",
"Kill it wherever it starts" and four like them; Hester (chat 166) four -- the
bell rope, the man with the nail satchel, the reed run, the chapped-face man;
the Doctor (the lookout story) three -- "learn who is [the watchman she
expects], and fast", "Ren went to the north windows first ... Ask her what's up
there", the north balcony door. Every new notebook entry carried an `until`:
57 of 57 in the play database's four bare chats (160, 161, 165, 166), 10 of 10
in the live database's two -- the reply's own example entry has the field, so
the field stopped telling anything apart.

What lasting aims there were lived elsewhere. Hester's authored aims are
intentions (`ia1` steer the inspection toward a natural foundering, `ia2`
protect Abel). At chat 166 turn 3 the read-back took the line "There is no
getting ahead of her to Abel; the only protection left is being in the room
when he talks" for giving `ia2` up -- the tactic died and took the aim with it,
the design note's "abandoned with the tactic". Later (turn 19) she wrote "I mean to
see that coat ashore whole and the man answered for by name, whatever it costs"
as a `changes` line, which can only become an intention -- and with four aims
held, it was turned away at the cap and lost (below). Sarah Moon's three authored aims (the intake
assessment, the stability evaluation, a calm tone) went dormant at full
progress at turns 19 and 22 (`stalled`) and nothing asked her what she was
about next: `dormant` was not a boundary.

The review beat fired on 13 calls over 11 of chat 166's 31 beats (Hester 9
calls over 8 beats, Abel 4 over 3), 9 of the calls to a mind holding nothing;
the section said "a turning point for the work you have taken on. Serve it,
finish it or set it aside". Under the shipped gating the take-up section ships
on 11 of those calls (2 of them to Hester holding one project) and the review
on 4.

## An aim with no room is kept, not dropped

An errand filed as an intention meets the intention ledger's own cap (four at
`ordinary`, `affect.capacity_caps`), and an add over it was turned away with a
commit warning and nothing else. Over the play database's 4,340 active commits:
38 adds turned away in 17 chats, 18 of them in the 75 commits of the four bare
chats (chat 165: five adds over four of its seven beats). Replayed through the engine's own
`apply_intent_ops` on the nine active-variant bare-era adoption beats, from
each beat's pre-turn checkpoint (play 165 t3/t4, 166 t3/t5/t8/t9; live 165
t1/t4/t5):

| | aims turned away and lost | kept as reminders |
|---|---|---|
| the beats as played | 4 (`changes` lines at 165 t3, t4 and live 165 t5) | -- |
| round one's patch (every adoption an intention, notebook adds first) | 7: Hester's two errands at 165 t3 and t4 outright, the three `changes` lines lost there as played, and an aim each errand pushed out at 166 t9 and live 165 t5 | -- |
| shipped (the line, closes first, no room kept) | 0 | 6 |

Under the shipped line one of the nine is a project ("Kill it wherever it
starts", 165 t4), seven errands become intentions, and six aims are kept as
reminders in their own words, where the mind sees them next beat
(`notebook.kept_when_no_room`) -- each once, against what the notebook will
hold after the beat's own ops: a mind that takes a kept aim up again strikes
or rewrites the reminder holding it in the same beat, and if the ledger is
still full, a reminder held at the start of the beat would stand in for the
aim and then be struck, leaving it in neither place. The compile also files
what an aim given up or finished closes ahead of the beat's new aims, so a
slot freed this beat is free for them. Of the 34 beats in the play database
where an add was turned away,
2 had filed it ahead of a close in the same reply, both Hester's in chat 166:
at turn 19 the lasting aim she voiced -- "I mean to see that coat ashore whole
and the man answered for by name, whatever it costs" -- was turned away while
the same reply finished `i6` after it. Filed closes first it lands, and at turn
2 "First light is fixed ..." does too.

## The line, probed

**The battery** (scripts kept with this lane's scratch, not shipped): 59
commitments with their ends, labelled by the owner's line, one labeller. 27
ways to an end: the full-card era's two shrine journeys, the containment work
and the informed choice; chat 99's p1 ("Complete Hinami's full rejuvenation
session", the corpus's only established project) and two single-session arcs
like it; the maze commission and the courier's walk to the shrine; four of the
engine's own examples; three aims Hester and Sarah held or voiced, with an end
round one wrote; round one's three replayed lasting entries; and -- since the
corpus holds almost none of the ruled class's plain cases -- eight written for
the battery (the injured carried to a doctor three ways, home twice, the bar, a
two-day journey, a cargo off before the tide). 27 errands: the bare-era
adoptions and commitments, round one's three replayed errands, the engine's own
"get the key back before dark", and seven written ones, three of them deferred
("Tomorrow at the market, ask Petch's wife ..."). Five genuinely either way,
reported and not scored: two standing tactics, a two-move plan, a single feed,
a single conversation that talks someone down.

**In situ**: 46 of them (14 ways to an end, 28 errands, 4 either way) asked
against a captured beat's own read-back state, rebuilt with the engine's code
(`holding_from`, `state_text` with the reply and its reasoning): the 19
commitments the bare corpus wrote, in their own beats; round one's six replayed
entries, in theirs; the full-card era's arcs and journeys written into a
captured beat of their own story (chat 135 turn 47, chat 137 turn 46 and chat
114 turn 12 are their own adoption beats; p1 and a rejuvenation package into
chat 113 turn 104; the shrine journeys into chat 114 turn 12); and the written
cases into a captured beat of their speaker, with a line of scene that makes
them true (Abel's hand laid open, Agent Diaz bleeding through the dressing).

| wording (English), `lasting` / `one_stretch` | in situ: ways kept, errands admitted | battery |
|---|---|---|
| round one: "It runs until what would end it comes about, over days or more, on many separate occasions; no one success along the way finishes it." / "One stretch of doing finishes it." | 5/14, 0/25 (p1 0.10, the arcs 0.02-0.11) | 11/27 ways kept |
| a course of steps "kept to through setbacks" / "One act settles it." (and two like it) | 7/8, 12-13/22 | 27-28/28, 12-16/24 |
| the errand side naming its risk: "One try settles it, whether it comes off or not." | -- | 28/28, 19-21/24 |
| "Getting there ..." / "One thing, done here and now." | 13-14/14, 0-1/28 (a deferred errand at 0.49-0.52) | 22-24/27, 2/27 |
| round two: "Getting there: what would end it lies at the end of a way you will keep going along -- to a place or through stages, however many steps it takes, past setbacks and changes of plan." / "One thing to do, done in one go." | 13/14, 2/28 (mean of eight asks) | 26/27, 2-3/27 (two runs) |
| shipped: "Getting there: it ends when you arrive where it leads -- a place, or the last of its stages -- however many steps it takes." / "One thing to do or find out, done in one go." | **14/14, 2/28** (four asks) | **27/27, 1/27** |

Under round two's wording, in situ: chat 99's p1 and the single-session arcs
0.93-1.00, the shrine journeys 0.97-0.99, the informed choice 0.91, the
injured carried to a doctor 0.59-0.64, a way home 0.73; a walk to the bar the
one miss (0.47). Under the shipped wording the fourteen read 0.68-1.00, and the
two errands read as ways are the three-minute observation window in the lift
(0.88 -- its end, "The gate opens at the shelter sublevel", is an arrival) and
an investigation whose end is reaching the terminal at the shelter (0.69, which
the circularity gate refuses). The brief's own errand, "Ringer or workman --
find out which", 0.33.

**The owner's own journeys, as classes.** That battery held one bar item and one
home item, and the re-review found the short ones a coin flip there: every
miss carried a deadline or waited on something. So each of the three journeys
`CLAUDE.md` names was written fourteen ways -- plain, with a deadline, deferred
("once", "when", "after", "tomorrow"), with a purpose, someone else taken,
first person, terse -- in each speaker's own world, plus seven other ordinary
journeys (the last train, the lighthouse, the ferry), 49 in all; and against
them 36 one-instance errands, deferred and not, 16 sharing a journey's words
("Ask at the bar whether anyone's seen Abel", "Before dark, ask Ren where the
nearest doctor is", "On the way home, leave the net money at Petch's door",
"Fetch the first-aid kit from the corridor locker"). Each was written into a
captured beat of its speaker (Hester Gale, chat 166 turns 7 and 16; the Doctor,
the lookout story turn 5 and Kirinoura turn 2; Sarah Moon, chat 160 turn 11 and
161 turn 20), the injured with a line of scene that makes them true, and asked
with the engine's own `nb:0:kind` and `nb:0:lasts`. The first screen chose
among wordings on alternate items of each class and checked the rest; later
screens read all of them, and the shipped wording reads the two halves alike
(English 23 of 25 and 24 of 24 journeys, errands 2 of 18 and 0 of 18;
Japanese 22 of 25 and 22 of 24, errands 3 and 0).

| wording | home | the bar | the injured to a doctor | other journeys | errands read as ways |
|---|---|---|---|---|---|
| round two's (eight asks) | 13/14 | 8/14 | 7/14 | 7/7 | 0/36 |
| shipped (four asks) | **14/14** | **13/14** | **13/14** | **7/7** | **2/36** |

Under the shipped wording the two misses are "A drink at the Anchor before I
face Coyle again", whose end is a drink had (0.17), and "Get Abel to a doctor
tonight, whatever he says about it" (0.49); the two errands read as ways are
many-step procedures ("Once the alarm stops, ring the duty officer and report
the breach", 0.79; "After the shift, write up the incident report", 0.65). The
re-review's eight phrasings and this doc's bar item all read 0.71-0.98, from
0.47-0.88. On the way there: dropping only "past setbacks and changes of plan"
kept 42-44 of the 49 but read 4-5 of the 28 stored errands as ways; naming the
end as arriving, with "one thing to do, done in one go" on the errand side,
kept 48 but read 7 of 28 stored errands as ways -- the corpus's investigations,
which "or find out" on the errand side keeps out. What that costs: of six
written long investigations, two whose end is one fact learned read as one go
("Uncover who in the Foundation signed Hinami's transfer order" 0.39, "Learn
what the anomaly wants before it surfaces again" 0.46; 0.54 and 0.56 under
round two's wording) and four stay ways (0.95-1.00); of four short ones, none
reads as a way ("Find out who rang the bell" 0.30, 0.57 before).

**What the stored adoptions now get.** Of the fifteen distinct bare-era
adoptions, read in situ under the shipped wording: thirteen are intentions
(at most 0.42); "Kill it wherever it starts" -- a standing vigilance over every
time the wreck-bell talk surfaces -- is a project (0.63), and so is the
three-minute observation window (0.88; 0.51 under round two's wording).

**Japanese** (`ja` pack), each wording on its own battery, minimal state -- no
Japanese story has played on the bare card, so nothing in situ. On the 59
translated: round one's wording kept 11 of 27 ways to an end; translating the
English structure clause by clause ("たどり着くこと：...") kept 27 of 27 and
admitted 11 to 20 of 27 errands; round two's "長い道のり：終わりとなることは、何歩も先、場所へ向かう道か段階を経る道の先にある。つまずいても計画を変えても、そこまで進み続ける。"
/ "今ここで、一度やれば済むひとつのこと。" kept 25 and admitted 3. On the class
battery, written in Japanese in the same shapes, it kept 26 of the 49 journeys
(home 5, the bar 7, the injured to a doctor 9, of 14 each) -- "長い", a long
road, was what a short way home failed. The shipped
"たどり着くこと：自分か連れて行く人が向かう先に着いたときに終わる――ある場所か、段階の最後。何歩かかっても。"
/ "ひとつの用事：することか確かめることを、一度やればそれで終わる。" keeps 44
(home 13, the bar 12, the injured to a doctor 12) and reads 3 of 36 errands as
ways, each a thing sent, left or fetched (知らせを送る 0.74, 網の代金を戸口に置いていく
0.66, 予備の櫂を取ってくる 0.52); on the 59, 26 of 27 kept and 3 of 27 admitted.
The arrival is read as a person's -- yours, or whoever you are taking --
because the plain arrival wording read a message reaching someone
("知らせが彼女に届いた") as a way to a place (6 of 36 errands). The Japanese
`note_kind` reads 42 of the 49 journeys as commitments; the other seven, the
injured carried to a doctor among them, never reach the deliberation.

**The circularity gate** (`affect.adoption_refusal`, similarity 0.4) refuses 4
of the 27 ways to an end on the 59-item battery: a shrine journey whose end
names the shrine (0.40), the containment work (0.40), a rejuvenation package
(0.50) and "Fetch the physician / the physician is here" (0.50). On the owner's
own journeys it decides the outcome: a journey's end names where it goes
("down to the Anchor" / "I'm at the Anchor"), and the gate refuses 32 of the 49
English phrasings (home 8, the bar 10, the injured to a doctor 9, other 5) and
26 of the 49 Japanese ones as circular. End to end -- the kind read as a
commitment, the deliberation, the gate -- 17 of 49 become projects in English
(13 under round two's wording) and 19 of 49 in Japanese (14), and no errand in
English, 2 of 36 in Japanese. What the gate is for holds: of 12 tasks whose end
restates them ("Understand the symbols / I understand the symbols", "Repair
the radio / the radio works"), the deliberation alone reads 9 as ways to an end
and the gate refuses 10; without it 29 more English journeys would become
projects, and 8 of those 12 tasks. In play it refused 17 adoptions, 4
distinct: the containment work (chat 84) and two single-session rejuvenation
arcs (chats 85-92 and 98-113, branch copies) -- ways to an end by the owner's
line -- and a single feed (chat 107). Both checks stay; whether the gate should
hold for a way to a place is the owner's question.

## Replayed

**The route the replays ran on was not the story's.** Chat 166's turns 1-24 and
Sarah Moon's chat 161 turn 20 were played on NanoGPT `z-ai/glm-5.3:thinking`
(`play/agent_models_before_openrouter.json`; `llm_capture` requested the
`:thinking` id) and reasoned 2,984-15,411 characters a call. At 21:34 on
2026-10-07 the story's routing moved to OpenRouter `z-ai/glm-5.3` at `medium`,
and its own turns 25-30 reasoned 316-1,702. Round one replayed on OpenRouter:
Hester at turns 3, 4, 16, 20, 21 and 22 and Sarah at turn 20 (all played on
NanoGPT's thinking variant), and Abel at turn 26 (played and replayed on
OpenRouter `z-ai/glm-5.2`, effort off). The OpenRouter route reasoned in the
same range on 2026-10-07 (the story's own turns 25-30) as on 2026-10-09 (the
replays): the drop in deliberation is the provider and model variant, not the
route degrading between the two days.

- **At `medium`, 25 calls, three successive wordings of the card: nothing taken
  up.** The minds revised the concerns and reminders they held and filed aims
  as `changes`; 0.1-0.8 thousand characters of reasoning a call, the same range
  as the story's own post-switch turns. The original captured card, replayed as
  a control, got 0.1 thousand.
- **At `high` (asked of the process only), 12 calls, 11 read back (one hit a
  decision-model rate limit), 5-12 thousand characters of reasoning: one
  adoption**, at Hester's turn 4 -- "See her paid out as a foundering: first
  light on the Blackreed, and the false shoal on the north approach set in
  Coyle's mind as the cause ..." until "Coyle files her report calling it
  accidental foundering and leaves Brackwater". Two caveats make it weaker
  evidence than it reads. The harness removed her turn-3 project and did not
  add the intention this engine files in its place. And the entry restates
  aims she already held: `ia1` (steer the inspection toward a
  natural-foundering explanation) and her held concern about planting the false
  shoal, which her reasoning cites -- `claim_similarity` 0.083 and 0.333, under
  both 0.4 gates -- so after adoption the same aim stands at two tiers and
  nothing reconciles them.
- **Rerun faithfully (round two): the turn-3 errand present as intention
  `i2`**, as the patched compile files it (closes first, a slot free), the
  current card with `project_take_up`, same route and effort: **no adoption in
  2 calls** (6.7 and 9.0 thousand characters of reasoning). In both she wrote
  the errand into her own bell reminder (`r1`); in one she added a worry about
  who else was aboard.

Read as fiction, round one's turn 4 is right -- she answers the bell question
truthfully because it costs nothing, keeps Coyle walking toward the rope, and
names the work under everything -- but as a measurement it is one call, in an
unfaithful counterfactual, re-filing an intention she held.

## Spend

Priced from each response's usage. Round one: about $0.53 of the lane's $0.80
(decision-model probes $0.04, 37 character calls about $0.40, their read-backs
about $0.09). Round two: about $0.24 of $0.40 -- some 2,600 decision-model
requests probing wordings ($0.20), and two character calls with their
read-backs ($0.035). Round three: about $0.35 of $0.40, all decision-model
requests (2,040 of them, 17,108 questions) measuring the owner's journeys as
classes in both packs; no character calls.

## What is left

- **The route for `character_major`.** NanoGPT's `z-ai/glm-5.3:thinking` (as
  chat 166's turns 1-24 were played: 3-15 thousand characters of reasoning a
  call), OpenRouter `z-ai/glm-5.3` at `medium` (now: 0.1-1.7 thousand; nothing
  taken up in 25 replayed calls) or at `high` (5-12 thousand; one adoption in
  twelve, in the unfaithful counterfactual, none in two faithful ones). The
  owner's.
- **The circularity gate decides the owner's journeys.** It refuses 32 of 49
  English and 26 of 49 Japanese phrasings of going home, to the bar and the
  injured to a doctor as circular -- a journey's end names where it goes -- so
  end to end 17 and 19 of the 49 become projects; in play it refused the
  containment work and two single-session arcs. Without it, 29 more English
  journeys and 8 of 12 tasks whose end restates them would be projects. Keep
  the 0.4 word overlap, exempt an end that is arriving where the way leads,
  or ask the decision model whether the end lies outside the doing.
- **An adoption that restates a held intention is not reconciled across
  tiers** (the turn-4 foundering entry and `ia1`).
- **Where the line still misses.** In English an end that is one act at a
  place ("A drink at the Anchor before I face Coyle again" / "I've had a drink
  at the Anchor", 0.17) and a deadline taken to a doctor (0.49); two many-step
  procedures read as ways; and an investigation whose end is one fact learned
  can read as one thing to find out -- of six written long investigations,
  "Uncover who in the Foundation signed Hinami's transfer order" 0.39 and
  "Learn what the anomaly wants before it surfaces again" 0.46, the other four
  0.95-1.00 -- the price of the errand side's "or find out", which keeps the
  corpus's investigations out. In Japanese five of the 49 journeys, three errands
  sent, left or fetched, and the Japanese `note_kind` reads seven of the 49
  journeys as something other than a commitment before the deliberation is
  asked.
- **Japanese is probed only on its own battery**, never in situ.
- **A kept reminder does not steer.** An aim with no room is kept in the
  notebook in its own words; it is not re-offered as an intention when a slot
  frees -- the mind takes it up again by writing it, or strikes it.
- **Probation and service are unmeasured under the bare contract**: nothing has
  been held long enough to establish or lapse, and the restored drift marker
  has never fired in the corpus.
