# Tavern scene-manager run — findings

7 turns (opening + 6), `zai-org/glm-latest` for every role, two full party
characters, the entire tavern populace invented on the fly by the Director.
`background_config.scene_life = "full"`, `max_managed = 6`. Auto-promotion off
so ambient chatter could not promote a barfly mid-test.

See `transcript.md` for the full run.

---

## What worked

**One call voices a whole room.** From turn 1 on, the manager held 5–6
presences and produced 2–3 acting each beat, the rest silent. The per-presence
architecture cannot do this: at `max_reactors: 1` it produces one line from one
presence, and each reactor is generated blind to the others.

**Extras talk to each other, not to the party.** This was the point of §0, and
it showed up immediately and consistently:

- t1 — *"Armed one's bandaged up proper. Wonder where they come from."*
- t3 — *"Two silver. That's what he charged the tinker's lot last month, wasn't it."*
- t4 — *"She's counting heads. See how she does that."*

None of these are addressed to the player. Every one is one extra muttering to
another *about* the party, which is the indifference texture the salience gate
structurally cannot produce.

**Turn 4 is the clearest single result.** The player does nothing — turns their
back and watches. The locals notice being watched and get wary; the old man
mutters to himself about the *barkeep's* line to a third party (*"Sticks, he
said. All of 'em stick, come the cold..."*); the card players act without
speaking and are explicitly described as paying her no mind. A beat with no
player salience at all became a populated room.

**Frozen blurbs drive both voice and conduct.** The old man's blurb says
*"creaking voice, too slow for conversation, trails off mid-thought"*, and his
lines do exactly that. Stronger still, t5: his frozen trait is *"resents anyone
blocking the fire or sitting close"*, Ysolde crouches beside him, and unprompted
he says *"Mind the draft, you're blocking it."* Nothing in the beat asked for
that — it came from the blurb.

**Blurb minting produced distinct people, not a matched set.** One batched call
per cohort, with existing blurbs passed as negative examples. Five presences,
five different registers, classes and temperaments. No homogenization observed.

**Silence is used well, and reads as characterization.** t3: the Director voiced
the barkeep's actual negotiation (correctly — it is plot), and the manager gave
him a *non-verbal* beat on top: *"Does not look up. Wipes the same spot on the
bar... the answer already given and not worth another word."* Two agents voiced
one person in complementary registers without colliding.

---

## Emergent behaviour

Not designed, observed:

1. **Chorus presences arose spontaneously.** The Director created "Table of
   Locals" and "Card Players" as *collective* entities and the manager voiced
   them as such. That is §4's chorus presence, unbuilt, arriving on its own.
2. **The narrator treated manager lines as compressible texture** — rendering
   them as trailing overheard fragments (*"Behind you, low and plain: ..."*)
   rather than dramatizing them as beats. This is the §3.4 narrator contract
   holding *without* the prompt clause that section says is required. It may
   still be needed under other conditions, but it was not needed here.
3. **Cross-agent conversational threading.** t4's old man continues a line the
   *barkeep* said to a *third party*, half to himself. Nobody wired that.
4. **A plot thread self-assembled out of a fabrication.** See below — this is
   both the most striking and the most dangerous thing in the run.

---

## The main problem: the manager invents world facts through its people

§3.12 draws the line at *the manager gets people, not events*. The schema
enforces the hard half (no `state_diff`, no new entities, no arrivals) and that
held all run. The **soft** half — speech asserting facts about the world — leaked
at roughly one small proper noun per turn.

Verified against the Director's own output (a string that never appears in
`director_resolve` for that turn is a manager invention):

| turn | manager line | in Director output? |
|---|---|---|
| 2 | "…That'd be **Tam Briddock's boy**, and…" | **no — invented** |
| 3 | "…what he charged **the tinker's lot last month**…" | **no — invented** |
| 5 | "She's at **the Widow** now." | yes — Director created `old_woman_hearth` named "The Widow" and voiced her that same beat |

So two of three are genuine inventions; the third was a false alarm on first
read and the manager was correctly echoing established canon.

**And then the fabrication was absorbed into canon.** "Tam Briddock's boy" was
invented by the manager on t2. By t6 the Director-voiced Widow says *"Ewe came
back alone. Drover's boy didn't."* — the invented detail has become the
dramatic spine of the scene, and the best beat of the run is built on it.

This is exactly the laundering path §3.9 and §3.12 warn about, and it produced
the best writing in the test. That tension is the real finding: **the mechanism
that makes the room feel alive is the same one that erodes the Director's
ownership of causality.** Suppressing it entirely would cost most of the texture.

**Recommended fix — treat manager assertions as claims, not facts.** The engine
already has this exact concept, applied to the player: `director_interpret`'s
Player Authority Contract records a player's claim about another character's
past words as *claimed, not established*, and lets the named party confirm,
correct or ignore it. Apply the same treatment to manager-voiced lore: an
extra's assertion about the world is a **claim** the Director may ratify or
quietly drop. That keeps the texture, keeps the Director as sole ratifier, and
reuses machinery that exists rather than adding a suppression rule.

---

## Other issues found

**Information-barrier hole in the prototype (fixed).** Admission control covered
`dialogue_log` but not `resolved_event`. The Director's prose is authored from
the omniscient objective frame and can restate a concealed line verbatim — the
per-presence path has always redacted this (`_beat_for_presence`), the manager
path passed the prose raw. Fixed by `_redacted_resolved_event`, with two tests.
Found by live play, not by the tests, because the tests only exercised
`dialogue_log`.

**The catchphrase risk is real and arrived on schedule.** §3.8 predicted a
frozen `tell` would become a stuck animation. The Serving Girl tucked a loose
strand of hair behind her ear on t1, t3 and t6 — every single turn she acted.
This is the prompt-level fix §3.8 anticipated (the tell is *available colour*,
not a required beat; the `recent` tail should suppress an immediate repeat), and
it should be made before this is used in earnest.

**Presence-name fragmentation.** The Director renamed the hearth figure from
"Old Man by the Hearth" to "The Old Man" on t6, creating a second tracked
presence with no blurb and no history. `track_background_presences` already
folds entity-id → display-name for the same class of problem; it needs an
equivalent fold for a display-name change on a stable entity id.

**The manager does not exclude presences the Director already voiced this
beat.** `pick_background_reactors` excludes `voiced_this_beat`;
`managed_presences` deliberately does not, because the manager should be able to
add a non-verbal beat on top (t3's barkeep, which worked well). The model
avoided double-voicing on its own every turn, but nothing enforces it.

**Cost.** 170–720s per turn, rising with scene complexity — but the manager is
one call among ~10 in a turn, and it replaces N per-presence calls. The blurb
mint is one call per new cohort, not per turn.

---

## Verdict

The core hypothesis holds: one LLM given a location and a short-context roster
keeps a room alive in a way the per-presence architecture structurally cannot,
and frozen blurbs are enough to make extras recognizable across turns without
giving them memory or psychology.

The blocker for anything beyond a prototype is the claims-vs-facts problem
above. It is a real erosion of the Director's ownership, it is happening every
turn, and it has a clean fix that reuses existing machinery.
