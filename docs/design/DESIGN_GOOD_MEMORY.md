# Good memory: what people do that characters could

**Status: PROPOSAL, 2026-09-26, branch `worktree-jev-character-tracking`.**
What is unbuilt is registered in [`UNBUILT_CHARACTERS.md`](../UNBUILT_CHARACTERS.md)
§6.16, not here. Evidence: [`JEV_MEMORY_PROBE_2026_09_26.md`](../experiments/JEV_MEMORY_PROBE_2026_09_26.md).
Companion: [`DESIGN_JEV_CHARACTER_PASS.md`](DESIGN_JEV_CHARACTER_PASS.md).

## The goal, and what it rules out

The owner, 2026-09-26: "I'm focused on good memory not realistic forgetting as
that is an entirely different goal." And, rejecting a lower-resolution
periphery for the packet: "peopel can sift through memory really rapidly if
they need to... but our characters have to deliberate recall to do that so
lowering resolution may hurt our goal of imitation."

So a feature belongs here if it puts the RIGHT memory in front of a character
at the right moment, IN FULL, or lets the character reach it when it needs to.
The features of human memory that are about losing things are listed at the
end, set aside, so they are not proposed again as memory improvements.

What is already measured (the evidence doc): a Jev-filtered packet carries
about 2.5 times the relevant rows of today's recall, judged blind by two
judges; at 48 rows it still carries fewer irrelevant rows than today's 24; the
strongest lanes of a fitted net were the previous beat's picks, their
neighbours, and the character's unsettled concerns; mood contrast needed a tag
written once at commit.

## The features

Each gives what people do, with the finding it rests on; what it would be
here; and how it would be measured. None grants a mind anything it did not
already hold: every one reads the character's own visible bank through the
seam today's recall uses (`visible_memory_rows`), so the firewall is where it
was.

### 1. Sifting within the moment

**People.** Retrieval is a cycle: a cue brings back a fragment, the fragment
becomes the next cue, and a specific memory is reached in seconds -- the
"generative retrieval" of Conway and Pleydell-Pearce's self-memory system
(Psychological Review, 2000).

**Here.** A ponder is set on one beat and answered on the next, so a character
cannot sift at all; a ponder fires about one beat in 332. Jev reads a 650-row
bank in about half a second, so a recall the character asks for DURING its
call could come back before the call finishes, in full, and be followed by a
second ask. The engine has no model tool-calling loop (every model call is
single-shot JSON), so this is new plumbing in the character call. It is the
feature that answers the owner's objection, and the reason the packet's
periphery is not gisted.

**Measure.** Conduct replays where the memory a beat needs is outside the
packet: does the character reach it, and does the beat read better?

### 2. More memories, organized by why they are there

**People.** Experts hold far more than a few items "in mind" by organizing
them into retrieval structures -- long-term working memory (Ericsson and
Kintsch, Psychological Review, 1995). Organization, not count, is what makes a
large store usable in the moment.

**Here.** Grow the packet -- a 48-row Jev packet measured affordable on
relevance -- and section it by why each row is there: it bears on what is
happening; you promised it; you share it with someone here (`callback`); be
careful with it (`sore`); it felt like this moment; it felt the opposite.
Every row in full. The section is also the citation's context, which is what
frayed at 96 rows in `RETRIEVAL_COST.md` section 6.

**Measure.** The conduct replay in
[`MEASUREMENT_BACKLOG.md`](../experiments/MEASUREMENT_BACKLOG.md) §1, with
citation accuracy per section.

### 3. Activation that learns from use

**People.** How available a memory is tracks how likely it is to be needed:
each use raises it, and it falls as a power function of the time since use,
the same laws the environment's own recurrences follow (Anderson and Schooler,
"Reflections of the environment in memory", 1991). What is active spreads to
what is associated with it (Collins and Loftus, 1975). ACT-R's base-level
equation is the fitted form; its optimized-learning approximation needs only
the number of uses and the age: B = ln(n / (1 - d)) - d ln(L).

**Here.** A lane from columns the bank already stores (`access_count`,
`last_accessed_turn`, the row's turn), plus spreading from what is in view and
from the last beat's packet -- which is what the net's two strongest measured
lanes, `primed` and `primed_nb`, already approximate. Used to RANK only; no
retrieval threshold, since withholding is forgetting.

**Measure.** As a lane in `tools/jev_net_labels.py fit`: does it replace
`recency`, `primed` and `importance`?

### 4. Open intentions keep their memories close

**People.** Material tied to an intended, not-yet-done act stays more
accessible -- the intention-superiority effect (Goschke and Kuhl, JEP:LMC,
1993) -- and is released once the act is done (Marsh, Hicks and Bink, JEP:LMC,
1998).

**Here.** Link rows to the thread they serve -- an intention, a promise, a
project, an unresolved item -- boost them while it is open, release them when
it closes. The fitted net already gave "what is still unsettled" the heaviest
weight (3-5). Closing depends on the gap recorded in the Jev design note:
`waiting_ops` is taught and never compiled, so no character can give up on a
promise today.

### 5. Cues that bring memories back unbidden

**People.** Involuntary autobiographical memories are frequent and arrive
without search, cued by features the present shares with the past, sensory
ones above all (Berntsen, 1996; 2009); odours bring back older and more
emotional memories (Chu and Downes, 2000; Herz and Schooler, 2002).

**Here.** When a present sensation strongly matches a row -- the `senses`
channel, which a net of 100 already holds at 84-91% -- a small "this comes
back to you" section, beside the existing resurfacing lane
(`resurfaced_subject` in `build_character_memory_context`).

### 6. Mood-aware recall

**People.** Recall favours memories that match the current mood (Bower, 1981;
Blaney, 1986), and people in a low mood often reach next for a happy one --
mood repair (Josephson, Singer and Salovey, 1996) -- less so when depressed.

**Here.** The split between `mood_match` and `mood_contrast` rows set by the
character's state: under stress a vulnerable mind's packet leans congruent, a
steady one's reaches for repair. Derived from stress and the sheet already
filled, not a new card field -- an empty card field fails silently. Needs the
moment tag (the Jev note's decision 5).

### 7. What surprised them stays sharp

**People.** What breaks an expectation is remembered better -- the isolation
effect (von Restorff, 1933), and expectancy-incongruent information about a
person (Stangor and McMillan, Psychological Bulletin, 1992).

**Here.** One Jev question at commit, "did this surprise you?", raises the
row's standing, at about $0.00001 a row.

### 8. The memories a life is about

**People.** Self-defining memories are vivid, emotional, recalled again and
again, and tied to a person's enduring concerns (Singer and Salovey, 1993);
the working self's goals gate what is retrieved (Conway and Pleydell-Pearce,
2000).

**Here.** A Jev tag at commit: does this bear on what you are fundamentally
about -- the drive, a project? Those rows keep a durable place and a section of
their own. Only as good as the drive; an empty drive is the worst authoring
failure the engine has measured (CLAUDE.md).

### 9. What I know about someone

**People.** Memory about people is organized around the person: observations
are integrated into a representation of them (Hastie and Carlston, "Person
Memory", 1980).

**Here.** A consolidated dossier per person the character knows, answering
"what do I know about X" -- the weakest ponder kind measured (61% of the best
answers in a pool of 50). It needs identity resolved at ingest from the
holder's own knowledge: rows still say "the beautiful young woman" long after
The Doctor learned her name. Rows join a name only once the holder has
learned it -- which keeps the firewall's line exactly where it is.

### 10. Who else would remember

**People.** Couples and teams remember as a system: each knows who knows what,
and retrieval routes through the others (Wegner, transactive memory, 1987).

**Here.** From each row's participants, a note of who else was there, so
asking a companion becomes a move the character can see. It is the
character's own record of who was present; nothing new crosses.

### 11. Consolidation that organizes

**People.** Sleep strengthens and reorganizes memory, favouring what will be
needed later (Diekelmann and Born, Nature Reviews Neuroscience, 2010; Wilhelm
et al., Journal of Neuroscience, 2011).

**Here.** When a character sleeps: merge near-duplicate rows (the plateau's
repeated scene descriptions), link episodes into events, refresh the summary
windows as an index over raw memory ([`UNBUILT_CHARACTERS.md`](../UNBUILT_CHARACTERS.md)
§2.16). Organize; never erase.

### 12. What is true now, first

Not a borrowed finding but a measured failure: Jev judges whether a memory is
ABOUT something, not whether it is still true ("Where is the TARDIS right
now?" returned where it WAS). Good memory hands over the current state first.
That is [`UNBUILT_CHARACTERS.md`](../UNBUILT_CHARACTERS.md) §2.24 (a superseded
belief is read before its correction), and a larger packet makes it more
urgent.

## Set aside by the goal

Realistic forgetting, not good memory, so not proposed here: gist in place of
detail, tip-of-the-tongue and familiarity without recollection, the fading
affect bias, source-monitoring blur and the sleeper effect, motivated
forgetting, retelling drift, and any retrieval threshold that withholds a row.
They would return only under a separate goal of their own.

Not re-proposed either: embedding a hypothetical answer (HyDE) was rejected on
2026-08-20 for breaking more hits than it rescued
([`UNBUILT_CHARACTERS.md`](../UNBUILT_CHARACTERS.md) §2.25). The 2026-09-26
question experiment gave it +3 to +5 points without measuring breakage, which
does not reopen it; a ponder is better served by Jev reading the whole bank.

## Where to start

1. **Sifting (1) and organized, larger packets (2)** -- the owner's two
   points, and the conduct replay decides the size.
2. **Activation (3)** -- arithmetic on stored columns; may retire three lanes.
3. **The moment tag**, which feeds mood-aware recall (6) and unbidden cues (5).
4. **Dossiers (9)**, once identity is resolved at ingest.

Retrieval-side features are scored as lanes in `tools/jev_net_labels.py fit`
and blind with `tools/jev_packet_compare.py`; conduct only by replay and by
reading the page -- [`UNBUILT_CHARACTERS.md`](../UNBUILT_CHARACTERS.md) §2.17's
"evaluate behaviour, not only answers".
