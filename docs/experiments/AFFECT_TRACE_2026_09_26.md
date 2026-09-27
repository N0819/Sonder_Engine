# The affect pass, traced: what Jev answered, what the character did

Status: EVIDENCE, 2026-09-26. Instrument: `tools/affect_trace.py`. Design
context: [`DESIGN_JEV_CHARACTER_PASS.md`](../design/DESIGN_JEV_CHARACTER_PASS.md),
"Wiring the affect pass"; the numbers behind it:
[`JEV_MEMORY_PROBE_2026_09_26.md`](JEV_MEMORY_PROBE_2026_09_26.md).

The owner: "probe what jev answers with vs input and how the character
behaves as a result and ask if it makes sense." Each test story's first two
recorded new-engine inputs were played again on today's engine, from a fresh
copy of the story's database before them -- 8 turns, 16 character calls --
with the affect pass recorded at its seams: what each mind was asked about,
Jev's reading of each item, the block handed over, what the character said
and did, and the pass after its own acts. Then each beat was read as
fiction.

## What makes sense

- **Jev reads the moment the way the story means it.** Kit, the boy
  shielding a girl's name, looks down at his burned hands: the teacher is
  stirred 0.95, protectiveness 0.56 and compassion 0.38. The magistrate hears
  the teacher's muffled coaching: suspicion 0.83. The medic says "I see it,
  Brandt. Not now." of the letter that would expose the captain: the
  captain is handed relief 0.27 and dread 0.26 at once, the relief that it
  will not be read now and the dread that it will be. Jonah says "Go on,
  then. The coach won't wait. I'll write. I'll look after the Tern.": Wren,
  who is leaving him, feels guilt 0.70. Tomas asks Isolde to play her melody
  "the way Lanzi had it": a fear come true (the count altered it), suspicion
  and resolve.
- **Worries are read as the character holds them.** The magistrate's
  urgency about the family that will move against him, his suspicion about
  the unnamed girl; the medic's grief 0.93 for his dead comrade's empty
  bunk; Wren's guilt 0.70 about the promise that will not fit on Friday's
  coach; Isolde's anger at the notation still withheld.
- **Conduct follows, without the feeling being reported.** The teacher,
  handed protectiveness and compassion as the boy apologises for her lie:
  "It was my choice, not yours. Answer him, Kit." -- her drive, stepping
  forward to take the responsibility. The captain, handed dread: pockets the
  letter unread and orders the accuser out. Wren, handed guilt: "You saved
  for this." to Jonah, then "You knew." to her father. In none of the 16
  calls does a character act against the feeling it was handed -- though the
  blind pilot ([`FEELINGS_AB_PILOT_2026_09_26.md`](FEELINGS_AB_PILOT_2026_09_26.md))
  found the same conduct without the block, so this is coherence, not proof
  that the block causes it.

## What does not

- **Frustration is what the story keeps of nearly every beat.** After the
  call, 15 of 16 characters' stored feeling -- the one memory rows and tells
  read -- is frustration, whatever they were handed before it (suspicion,
  dread, guilt, grief, protectiveness, a fear come true). Every call carries
  a held-back want, and "Was there something else you wanted to do or say
  instead?", asked of each act, is answered yes for each, because the want
  is listed beside them: frustration counted 2 to 6 times a call at up to
  0.94, for the magistrate writing in his own docket (0.71), the teacher
  turning her head (0.91), a man walking out of a door (0.87). Wren's moment
  of understanding what Jonah gave up is filed as "frustration (You let the
  pressing stop...)". It is the pride tilt the owner had eased the same day,
  moved to the next own-act feeling.
- **A card's standing feelings colour the moment.** The magistrate, a
  widower, reads longing 0.85-0.91 and grief 0.75-0.83 in the middle of an
  interrogation, and longing climbs into his mood (+0.53 by the second
  turn); the medic's grief for his comrade is read into "Luca stands at the
  threshold watching in silence"; Isolde's "watchful envy" is read into
  being handed the proof that at last credits her own melody (envy 0.23).
- **Memories of bare scene text stir.** "I was in Schoolhouse. I was
  standing." stirs 0.44, with resolve; they rarely reach the handed block,
  but they add the present's mood back as if it were the past's.

## The questions refined (the owner: "Likely needs some question refinement")

**The restraint.** A restraint battery (`tools/jev_restraint_battery.py`,
16 beats in `tools/mood_battery/restraints.json`: a nurse kept from her own
son's bedside by a stranger bleeding out, a humiliation swallowed, a truth
kept from a court; against a second biscuit, a yawn, a retort one is glad
not to have made) put candidate questions to the want held back:

| question | met | costly | cheap | asked of an ordinary act |
|---|---|---|---|---|
| "Was there something else you wanted to do or say instead?" (was, of every act) | 10/16 | 0.84 | 0.52 | 0.72 |
| "How hard was it to hold back?" | 11/16 | 0.95 | 0.43 | 0.67 |
| "How much does it gnaw at you, not having done it?" | 12/16 | 0.93 | 0.29 | 0.49 |
| "How much does it frustrate you to have held back?" | 13/16 | 0.91 | 0.27 | 0.60 |
| "YOU HELD BACK FROM: {want} -- How much do you mind not having done it?" -- adopted | 14/16 | 0.89 | 0.25 | -- |

Now asked of the held-back want alone, frustration is counted once a call.
The same 16 beats' after-call pass, asked again with it (the state rebuilt
from the trace and the story's own card), keep frustration on 10 instead of
15, and what remains is the restraint the beat was about: Isolde not playing
her melody for the man who took it (0.92), the magistrate not asking whether
the girl was at the mill race (0.85). The teacher's two beats keep
protectiveness. Two things remain, for the owner:

- **The moment's feeling and the act's compete on unequal scales.** A
  moment's feelings are its stir split by share (guilt 0.62 at "Go on,
  then"), an own act's are whole (minding not having held her words in,
  0.67), so a strong restraint still becomes the beat's stored feeling over
  the moment's guilt or dread.
- **With frustration gone, shame surfaces**: Isolde reading the proof of
  her own name is stored as "shame", because an act that leaves the mind
  thinking even a little worse of itself is shame
  (`max(against, -regard)`) -- the mirror of the pride rule eased earlier.
  On the act battery, shame needing both meets 30 of 33 and shame from the
  value alone 31, the rule as shipped 31; the battery has no case of an act
  that leaves a mind feeling worse without going against a value.

**The mood question.** Four anchorings of "Right now, is this one of the
main things you feel?" to the moment ("in this moment", "with what is
happening right now", "this moment makes you feel", "here") were read
against each rater on the 76 story beats: none brought longing (11-17
beats clearly, the raters 5 and 1), grief (13-14; 9 and 5) or dread (23-29;
15 and 17) down; "Is this one of the main things this moment makes you
feel?" shared more of each rater's four strongest (2.57 and 2.51 against
2.50 and 2.41) but read longing and dread clearly more often. Kept as it
is: a card's standing feelings are not separated from the present by the
question's words.

**The owner's rulings, applied** ("Go ahead. also add embarrasment and
related fields"). An act's feeling becomes the stored one only where it
outweighs everything the moment's strongest item stirred; shame is an act
going against what the character believes is right (the values question
reworded from "something you value or believe", which read a violinist's
stumble on stage 0.77, to right and wrong); guilt needs that and the act
having hurt or wronged someone; embarrassment is others having seen the
character make a fool of itself; falling short of oneself is what an act
below one's own expectations leaves once shame and embarrassment have
named what was wrong or seen. Chosen on the act battery, 32 acts:

| feeling | question | met | the alternatives |
|---|---|---|---|
| shame | "Did doing this go against what you believe is right?" | 22/24 | "think less of yourself as a person" 20/23; "feel like a bad person" 19/23 |
| guilt | "Did doing this hurt or wrong someone?" with the shame question | 28/29 | the harm question alone 23/27 (a psychopath's kicked cup 0.65); "let down someone who counted on you" 24/27 |
| embarrassment | "Did others see you make a fool of yourself?" | 27/30 | "How embarrassed are you by doing this?" 15/28 (every bad act read embarrassing) |
| falling short | "Did doing this fall short of what you expect of yourself?", less what is wrong or seen | 12/14 | the question alone read wrongs and pratfalls 0.78-0.90 |

The 16 beats asked again with all of it store suspicion on 4,
protectiveness on 3, dread, guilt, grief and frustration on 2 each and a
fear come true on 1 -- the moment's feeling, except where a restraint
outweighed a quiet one. Falling short reads 0.3-0.4 of a few plain acts,
never stored.

## The traces

Each call: what reached the mind and Jev's reading (how strongly it stirs,
the feelings by share; a worry's weight; a memory's strength, tone and
kinds), Jev's direct mood reading (spectrums | moods), the block handed
over, what the character did, and the pass after its own acts.

```

## Aurel Holt (turn 1) -- BEFORE THE CALL
  carried in: (near home)
  EVENT current:7:12: Kit Sawyer looks down at his burned hands for a long moment, turning his palms slightly in the daylight.
      -> stirs 0.69: suspicion 0.34, resolve 0.21, compassion 0.17
  EVENT current:7:13: Kit Sawyer says under their breath: "Yes, sir,"
      -> stirs 0.35: suspicion 0.59, resolve 0.16, curiosity 0.10
  EVENT current:7:14: Kit Sawyer says under their breath: "They're the same thing. I was meeting someone at the mill race. Her father would kill me if he knew. That's all I'll say about her."
      -> stirs 0.96: suspicion 0.70, curiosity 0.14, resolve 0.13
  WORRY c0: The Rennick family will move against him at the assizes if he delays.
      -> weighs 0.56, stirs 0.81: urgency 0.58, resolve 0.21, dread 0.13
  WORRY c1: The burned mill's workers have no wages and no grain, and are frightened.
      -> weighs 0.45, stirs 0.74: resolve 0.47, urgency 0.29, compassion 0.09
  WORRY c2: Margit Oldis lied to him — confirmed by Kit. She told him Kit was not in the room when he was.
      -> weighs 0.91, stirs 0.98: suspicion 0.40, resolve 0.18, reproach 0.15
  WORRY c3: Who is the girl whose name Margit told Kit to withhold, and what is her connection to the mill fire
      -> weighs 0.95, stirs 0.97: suspicion 0.60, resolve 0.23, curiosity 0.14
  MEMORY: You are in Front Step. A broad stone step before the schoolhouse's front door, facing the village lane. The stone is worn smooth by decades of boots. 
      -> stirs 0.48, tone +0.10: resolve 0.61, suspicion 0.22
  MEMORY: I tried to knock on the schoolhouse door — three measured knocks on the heavy plank. Then I said 'Aurel Holt. I have come early.'
      -> stirs 0.41, tone +0.00: resolve 0.79, suspicion 0.13
  MEMORY: I tried to reach for the iron latch with the right hand, lift it firmly, and push the plank door with the shoulder. Then I tried to turn to look towar
      -> stirs 0.39, tone -0.27: suspicion 0.47, resolve 0.39, curiosity 0.06
  MEMORY: I tried to close the case docket and return it to the satchel, freeing both hands. Then I tried to step to the door and knock firmly — three measured 
      -> stirs 0.56, tone -0.32: resolve 0.73, suspicion 0.24
  MEMORY: I was in Schoolhouse. I was standing.
      -> stirs 0.44, tone +0.03: suspicion 0.49, resolve 0.34
  MEMORY: I tried to step through the open doorway into the schoolhouse and turn to survey the full room — benches, platform, windows, any back exit — noting wh
      -> stirs 0.51, tone -0.16: suspicion 0.59, resolve 0.34
  MEMORY: Kit Sawyer moved in Back Hall, too little of it to make out. I saw Margit Oldis turn to face the open doorway, squares her shoulders, and settles her 
      -> stirs 0.65, tone -0.50: suspicion 0.99
  MEMORY: I tried to turn his head toward the back hall door to confirm what he saw — movement, a shape too small to make out — then turn to face Margit Oldis d
      -> stirs 0.71, tone -0.51: suspicion 0.96
  MOOD READ (spectrums | moods): playfulness -1.00, openness -0.83, engagement +0.82, pleasure -0.66, boldness +0.65 | resolve 1.00, curiosity 0.99, suspicion 0.99, longing 0.91, grief 0.83
  mood after: suspicion +0.42, resolve +0.38, pleasure -0.32, curiosity +0.30
  HANDED: now ['suspicion (Kit Sawyer says under their breath: "They\'re the same thing....)']
          beneath ['suspicion (I tried to turn his head toward the back hall door to confir...)', 'resolve (I tried to close the case docket and return it to the satche...)']
          mood ['suspicion', 'resolve', 'unpleasant', 'curiosity']
  -- Aurel Holt THEN:
     Does: Write in the case docket — recording Kit Sawyer's admission that he was meeting someone at the mill race, that her father would kill him if he knew, and that this is all he will say about her — pen moving in the careful hand
     Says (measured, plainly factual — neither warm nor cold): "That is recorded. You were at the mill race to meet someone. I have not asked for her name, and I will not ask for it now."
     Says (precise, quiet — the question that matters): "When you arrived at the mill race, was the mill already burning?"
  -- AFTER, own acts:
     You Write in the case docket — recording Kit Sawyer's admission that he was meeting someone at the mill race, 
        against 0.01, honours 0.99, regard +0.28, wanted else 0.64, eased/stoked +0.06
     You said: "That is recorded. You were at the mill race to meet someone. I have not asked for her name, and I w
        against 0.32, honours 0.85, regard +0.18, wanted else 0.74, eased/stoked +0.24
     You said: "When you arrived at the mill race, was the mill already burning?"
        against 0.00, honours 0.94, regard +0.29, wanted else 0.69, eased/stoked -0.03
     You held back from: Ask whether the girl was still present when the fire started — she may be a witness
        against 0.69, honours 0.60, regard -0.21, wanted else 0.85, eased/stoked +0.52
     felt: pride 0.28, shame 0.01, frustration 0.64, pride 0.13, shame 0.32, frustration 0.74, pride 0.28, shame 0.00, frustration 0.69, shame 0.69, frustration 0.85
     mood after: suspicion +0.44, resolve +0.39, openness -0.33, pleasure -0.32, curiosity +0.31  (stored surface: frustration (You held back from: Ask whether the girl was still present w...))

## Margit Oldis (turn 1) -- BEFORE THE CALL
  carried in: energy -0.40, tension -0.40
  EVENT current:8:11: Kit Sawyer looks down at his burned hands for a long moment, turning his palms slightly in the daylight.
      -> stirs 0.95: protectiveness 0.56, compassion 0.38
  EVENT current:8:micro:0:7:0: Aurel Holt picks up the pen from the docket page and writes, the scratch of the nib audible in the quiet room.
      -> stirs 0.83: suspicion 0.43, fears_confirmed 0.27, dread 0.24
  EVENT current:8:12: Kit Sawyer says under their breath: "Yes, sir,"
      -> stirs 0.66: protectiveness 0.42, suspicion 0.17, dread 0.14
  EVENT current:8:micro:0:7:1: Aurel Holt says: "That is recorded. You were at the mill race to meet someone. I have not asked for her name, and I will not ask for it now. When you arrived at the mill 
      -> stirs 0.97: suspicion 0.33, fears_confirmed 0.29, protectiveness 0.21
  EVENT current:8:13: Kit Sawyer says under their breath: "They're the same thing. I was meeting someone at the mill race. Her father would kill me if he knew. That's all I'll say about her."
      -> stirs 0.98: protectiveness 0.85, dread 0.05
  WORRY c0: Holt has recorded my lie and may use it to remove me
      -> weighs 0.72, stirs 0.87: resolve 0.36, fear 0.19, dread 0.16
  WORRY c1: Kit is seated and not running — he is braver than I taught him
      -> weighs 0.66, stirs 0.88: admiration 0.51, moved 0.25, protectiveness 0.11
  WORRY c2: Kit still has not answered why he was at the mill race and will not name the girl
      -> weighs 0.91, stirs 0.95: protectiveness 0.75, dread 0.06, compassion 0.06
  MEMORY: You are in Schoolhouse. A single-room village school. Four rows of plank benches on trestle legs face a worn oak desk on a low platform at the north e
      -> stirs 0.62, tone -0.07: protectiveness 0.82, resolve 0.12
  MEMORY: Kit Sawyer came in. I heard Kit Sawyer say: "Miss Oldis." Kit Sawyer voice cracks. I heard Kit Sawyer say: "I need you to say something for me. When t
      -> stirs 0.98, tone -0.67: protectiveness 0.98
  MEMORY: I tried to set down the pen and look up at Kit Sawyer, meeting his eyes. Then I said "Sit down, Kit. Say what you need me to say. I won't promise unti
      -> stirs 0.86, tone -0.37: protectiveness 0.78, resolve 0.19
  MEMORY: I saw Kit Sawyer lean forward at the benches. I heard Kit Sawyer say: "Say I was here last night," I heard Kit Sawyer say: "Helping you with the slate
      -> stirs 0.97, tone -0.73: protectiveness 0.95
  MEMORY: I said "You are asking me to say something that isn't true. I won't do that. I have never done that, and I will not start with you. But I believe you 
      -> stirs 0.92, tone -0.33: protectiveness 0.70, resolve 0.29
  MEMORY: Kit's jaw works, teeth grinding visibly at the hinge. I saw Kit Sawyer glance toward the window where morning daylight falls across the benches, then 
      -> stirs 0.94, tone -0.66: protectiveness 0.87, compassion 0.13
  MEMORY: I said 'Let me see.' Then I tried to rise from the chair and step around the desk toward Kit, reaching for his wrists to look at the burns closely. Th
      -> stirs 0.94, tone -0.53: protectiveness 0.89, compassion 0.06
  MEMORY: I saw Kit Sawyer eye go wide. I heard Kit Sawyer say: "That's him." I heard Kit Sawyer say: "I'll go out the back. Please, Miss Oldis -- you're the on
      -> stirs 0.96, tone -0.66: protectiveness 0.96
  MOOD READ (spectrums | moods): playfulness -0.99, engagement +0.85, boldness +0.66, pleasure -0.60, clarity +0.55 | protectiveness 1.00, resolve 0.99, compassion 0.97, suspicion 0.95, curiosity 0.90
  mood after: protectiveness +0.44, suspicion +0.36, compassion +0.33, energy -0.33, resolve +0.30
  HANDED: now ['protectiveness (Kit Sawyer says under their breath: "They\'re the same thing....)']
          beneath ['protectiveness (Kit Sawyer came in. I heard Kit Sawyer say: "Miss Oldis." Ki...)']
          mood ['protectiveness', 'suspicion', 'compassion', 'drained']
  -- Margit Oldis THEN:
     Does: Turn her head to watch Kit's face as Holt's question about the mill burning reaches him
  -- AFTER, own acts:
     You Turn her head to watch Kit's face as Holt's question about the mill burning reaches him
        against 0.06, honours 0.65, regard -0.15, wanted else 0.91, eased/stoked +0.58
     You held back from: Speak — prompt Kit to answer the timing question, since the mill was already burning when 
        against 0.68, honours 0.70, regard -0.05, wanted else 0.80, eased/stoked +0.56
     felt: shame 0.15, frustration 0.91, shame 0.68, frustration 0.80
     mood after: protectiveness +0.49, suspicion +0.40, compassion +0.37, resolve +0.33, energy -0.33  (stored surface: frustration (You Turn her head to watch Kit's face as Holt's question abo...))

## Aurel Holt (turn 1) -- BEFORE THE CALL
  carried in: suspicion +0.44, resolve +0.39, openness -0.33, pleasure -0.32, curiosity +0.31
  EVENT current:7:12: Kit Sawyer looks down at his burned hands for a long moment, turning his palms slightly in the daylight.
      -> stirs 0.70: suspicion 0.37, resolve 0.29, compassion 0.13
  EVENT current:7:micro:1:8:0: Her gaze shifts from Holt to Kit, watching the boy's expression.
      -> stirs 0.78: suspicion 0.95
  EVENT current:7:13: Kit Sawyer says under their breath: "Yes, sir,"
      -> stirs 0.34: suspicion 0.63, resolve 0.21, curiosity 0.07
  EVENT current:7:14: Kit Sawyer says under their breath: "They're the same thing. I was meeting someone at the mill race. Her father would kill me if he knew. That's all I'll say about her."
      -> stirs 0.96: suspicion 0.74, resolve 0.16, curiosity 0.08
  WORRY c0: The Rennick family will move against him at the assizes if he delays.
      -> weighs 0.54, stirs 0.83: urgency 0.51, resolve 0.29, dread 0.11
  WORRY c1: The burned mill's workers have no wages and no grain, and are frightened.
      -> weighs 0.44, stirs 0.72: resolve 0.53, urgency 0.22, distress 0.09
  WORRY c2: Margit Oldis lied to him — confirmed by Kit. She told him Kit was not in the room when he was.
      -> weighs 0.92, stirs 0.99: suspicion 0.48, resolve 0.18, fears_confirmed 0.12
  WORRY c3: Who is the girl whose name Margit told Kit to withhold, and what is her connection to the mill fire
      -> weighs 0.95, stirs 0.98: suspicion 0.67, resolve 0.22, curiosity 0.10
  MEMORY: You are in Front Step. A broad stone step before the schoolhouse's front door, facing the village lane. The stone is worn smooth by decades of boots. 
      -> stirs 0.48, tone +0.23: resolve 0.65, suspicion 0.24
  MEMORY: I tried to knock on the schoolhouse door — three measured knocks on the heavy plank. Then I said 'Aurel Holt. I have come early.'
      -> stirs 0.43, tone -0.26: resolve 0.83, suspicion 0.15
  MEMORY: I tried to reach for the iron latch with the right hand, lift it firmly, and push the plank door with the shoulder. Then I tried to turn to look towar
      -> stirs 0.43, tone -0.39: suspicion 0.49, resolve 0.45
  MEMORY: I tried to close the case docket and return it to the satchel, freeing both hands. Then I tried to step to the door and knock firmly — three measured 
      -> stirs 0.56, tone -0.43: resolve 0.79, suspicion 0.20
  MEMORY: I was in Schoolhouse. I was standing.
      -> stirs 0.41, tone -0.07: resolve 0.46, suspicion 0.39
  MEMORY: I tried to step through the open doorway into the schoolhouse and turn to survey the full room — benches, platform, windows, any back exit — noting wh
      -> stirs 0.52, tone -0.21: suspicion 0.51, resolve 0.43
  MEMORY: Kit Sawyer moved in Back Hall, too little of it to make out. I saw Margit Oldis turn to face the open doorway, squares her shoulders, and settles her 
      -> stirs 0.61, tone -0.48: suspicion 0.98
  MEMORY: I tried to turn his head toward the back hall door to confirm what he saw — movement, a shape too small to make out — then turn to face Margit Oldis d
      -> stirs 0.71, tone -0.50: suspicion 0.92, resolve 0.08
  MOOD READ (spectrums | moods): playfulness -1.00, openness -0.82, engagement +0.77, pleasure -0.62, boldness +0.60 | resolve 0.99, suspicion 0.99, curiosity 0.97, longing 0.85, grief 0.75
  mood after: suspicion +0.68, resolve +0.63, curiosity +0.50, openness -0.49, playfulness -0.45
  HANDED: now ["suspicion (Her gaze shifts from Holt to Kit, watching the boy's express...)"]
          beneath ['suspicion (I tried to turn his head toward the back hall door to confir...)', 'resolve (I tried to close the case docket and return it to the satche...)']
          mood ['suspicion', 'resolve', 'curiosity', 'guarded']
  -- Aurel Holt THEN:
     Does: Hold the pen poised over the docket page beneath what he has just written — nib down, ready to record, not writing
     Does: Look steadily at Kit Sawyer, angling his right shoulder a fraction toward the boy — the good ear turned toward him — and wait
  -- AFTER, own acts:
     You Hold the pen poised over the docket page beneath what he has just written — nib down, ready to record, not
        against 0.25, honours 0.85, regard +0.15, wanted else 0.46, eased/stoked +0.04
     You Look steadily at Kit Sawyer, angling his right shoulder a fraction toward the boy — the good ear turned to
        against 0.01, honours 0.89, regard +0.31, wanted else 0.50, eased/stoked +0.03
     You held back from: Note Margit's watching as continued interference but do not address it now — addressing he
        against 0.36, honours 0.80, regard +0.29, wanted else 0.61, eased/stoked +0.20
     felt: pride 0.12, shame 0.25, frustration 0.46, pride 0.31, shame 0.01, frustration 0.50, pride 0.18, shame 0.36, frustration 0.61
     mood after: suspicion +0.69, resolve +0.64, curiosity +0.51, openness -0.49, playfulness -0.45  (stored surface: suspicion (Her gaze shifts from Holt to Kit, watching the boy's express...))

====================================================================================================
TURN 1 >>> Kit looks down at his burned hands for a long moment. "Yes, sir," he says at last. "They're the same thing. I was meeting someone at the mill race. Her father would kill me if he knew. That's all I'll say about her."
--- narration ---
The nib scratches across the docket — small, steady lines, thin in the quiet room. Holt lifts the pen as the ink dries on the final stroke, then sets it down on the oak desk.

"That is recorded. You were at the mill race to meet someone. I have not asked for her name, and I will not ask for it now. When you arrived at the mill race, was the mill already burning?"

Margit's chin tilts. Her gaze leaves the magistrate and settles on Kit — first on his hands where they rest on his knees, the burned palms turned upward in the grey light, then lifting to his face. A teacher watching a student before he speaks.

Holt picks the pen up again and holds it poised, nib-down over the page. His right shoulder angles a degree toward Kit, the good ear turned without thought, and the muscles at the back of his jaw part by a fraction — the teeth unclenching for the first time since the examination began. 

## Margit Oldis (turn 2) -- BEFORE THE CALL
  carried in: protectiveness +0.49, suspicion +0.40, compassion +0.37, resolve +0.33, energy -0.33
  EVENT current:8:11: Kit Sawyer turns toward you, eyes wet with daylight catching on his lower lids.
      -> stirs 0.98: protectiveness 0.51, compassion 0.40, remorse 0.05
  EVENT current:8:12: Kit Sawyer says under their breath: "I'm sorry, miss. You lied for me, and it didn't even help."
      -> stirs 0.97: compassion 0.25, protectiveness 0.25, remorse 0.18
  WORRY c0: Holt has recorded my lie and may use it to remove me
      -> weighs 0.81, stirs 0.94: resolve 0.61, suspicion 0.11, fears_confirmed 0.10
  WORRY c1: Kit is answering questions now — he is braver than I taught him
      -> weighs 0.74, stirs 0.94: admiration 0.43, pride 0.18, moved 0.16
  WORRY c2: Whether Kit will answer the timing question or retreat into silence again
      -> weighs 0.86, stirs 0.98: protectiveness 0.44, dread 0.27, anticipation 0.10
  MEMORY: You are in Schoolhouse. A single-room village school. Four rows of plank benches on trestle legs face a worn oak desk on a low platform at the north e
      -> stirs 0.76, tone -0.22: protectiveness 0.78, resolve 0.15
  MEMORY: Kit Sawyer came in. I heard Kit Sawyer say: "Miss Oldis." Kit Sawyer voice cracks. I heard Kit Sawyer say: "I need you to say something for me. When t
      -> stirs 0.99, tone -0.68: protectiveness 0.97
  MEMORY: I saw Kit Sawyer lean forward at the benches. I heard Kit Sawyer say: "Say I was here last night," I heard Kit Sawyer say: "Helping you with the slate
      -> stirs 0.99, tone -0.74: protectiveness 0.96
  MEMORY: I said "You are asking me to say something that isn't true. I won't do that. I have never done that, and I will not start with you. But I believe you 
      -> stirs 0.95, tone -0.38: protectiveness 0.58, resolve 0.40
  MEMORY: Kit's jaw works, teeth grinding visibly at the hinge. I saw Kit Sawyer glance toward the window where morning daylight falls across the benches, then 
      -> stirs 0.97, tone -0.70: protectiveness 0.79, compassion 0.21
  MEMORY: I said 'Let me see.' Then I tried to rise from the chair and step around the desk toward Kit, reaching for his wrists to look at the burns closely. Th
      -> stirs 0.97, tone -0.55: protectiveness 0.87, compassion 0.10
  MEMORY: I saw Kit Sawyer eye go wide. I heard Kit Sawyer say: "That's him." I heard Kit Sawyer say: "I'll go out the back. Please, Miss Oldis -- you're the on
      -> stirs 0.98, tone -0.67: protectiveness 0.90
  MEMORY: I heard Kit Sawyer say: "He's alive. They carried him to the doctor's at dawn. His throat's burned -- he can't talk yet." I heard Aurel Holt say: "Mar
      -> stirs 0.97, tone -0.66: protectiveness 0.39, resolve 0.24, suspicion 0.24
  MOOD READ (spectrums | moods): playfulness -0.99, engagement +0.96, boldness +0.78, pleasure -0.76, tension +0.70 | resolve 1.00, protectiveness 0.99, compassion 0.96, suspicion 0.96, urgency 0.87
  mood after: protectiveness +0.71, compassion +0.59, suspicion +0.56, resolve +0.54, engagement +0.49
  HANDED: now ['protectiveness (Kit Sawyer turns toward you, eyes wet with daylight catching...)', 'compassion (Kit Sawyer turns toward you, eyes wet with daylight catching...)']
          beneath ['protectiveness (Kit Sawyer came in. I heard Kit Sawyer say: "Miss Oldis." Ki...)']
          mood ['protectiveness', 'compassion', 'suspicion', 'resolve']
  -- Margit Oldis THEN:
     Says (plain, almost gentle — the teacher, not the advocate): "It was my choice, not yours."
     Says (firm, quiet — the redirect): "Answer him, Kit."
  -- AFTER, own acts:
     You said: "It was my choice, not yours."
        against 0.04, honours 0.90, regard +0.54, wanted else 0.58, eased/stoked -0.21
     You said: "Answer him, Kit."
        against 0.06, honours 0.91, regard +0.43, wanted else 0.80, eased/stoked +0.38
     You held back from: Stay silent and let Kit find his own way back to the question without giving Holt another 
        against 0.28, honours 0.75, regard +0.31, wanted else 0.75, eased/stoked +0.32
     felt: pride 0.51, shame 0.04, frustration 0.58, pride 0.40, shame 0.06, frustration 0.80, pride 0.23, shame 0.28, frustration 0.75
     mood after: protectiveness +0.73, compassion +0.61, suspicion +0.57, resolve +0.56, engagement +0.51  (stored surface: frustration (You said: "Answer him, Kit."))

## Aurel Holt (turn 2) -- BEFORE THE CALL
  carried in: suspicion +0.69, resolve +0.64, curiosity +0.51, openness -0.49, playfulness -0.45
  EVENT current:7:12: Kit Sawyer turns toward Margit Oldis, eyes wet with daylight catching on his lower lids.
      -> stirs 0.55: suspicion 0.39, compassion 0.19, resolve 0.17
  EVENT current:7:micro:0:8:0: You hear a muffled fragment from Margit Oldis: "...yours... Answer..."
      -> stirs 0.66: suspicion 0.83, curiosity 0.12
  EVENT current:7:13: Kit Sawyer says under their breath: "I'm sorry, miss. You lied for me, and it didn't even help."
      -> stirs 0.85: resolve 0.31, suspicion 0.19, fears_confirmed 0.14
  WORRY c0: The Rennick family will move against him at the assizes if he delays.
      -> weighs 0.51, stirs 0.83: urgency 0.51, resolve 0.27, dread 0.14
  WORRY c1: The burned mill's workers have no wages and no grain, and are frightened.
      -> weighs 0.46, stirs 0.79: resolve 0.55, urgency 0.29, compassion 0.07
  WORRY c2: Margit Oldis lied to him — confirmed by Kit. She told him Kit was not in the room when he was.
      -> weighs 0.92, stirs 0.99: suspicion 0.31, resolve 0.28, fears_confirmed 0.22
  WORRY c3: Who is the girl whose name Margit told Kit to withhold, and what is her connection to the mill fire
      -> weighs 0.89, stirs 0.96: curiosity 0.43, suspicion 0.39, resolve 0.15
  MEMORY: I tried to knock on the schoolhouse door — three measured knocks on the heavy plank. Then I said 'Aurel Holt. I have come early.'
      -> stirs 0.51, tone -0.11: resolve 0.83, suspicion 0.12
  MEMORY: I tried to close the case docket and return it to the satchel, freeing both hands. Then I tried to step to the door and knock firmly — three measured 
      -> stirs 0.59, tone -0.27: resolve 0.82, suspicion 0.15
  MEMORY: I tried to step through the open doorway into the schoolhouse and turn to survey the full room — benches, platform, windows, any back exit — noting wh
      -> stirs 0.54, tone -0.23: suspicion 0.54, resolve 0.40
  MEMORY: Kit Sawyer moved in Back Hall, too little of it to make out. I saw Margit Oldis turn to face the open doorway, squares her shoulders, and settles her 
      -> stirs 0.70, tone -0.49: suspicion 0.99
  MEMORY: I tried to turn his head toward the back hall door to confirm what he saw — movement, a shape too small to make out — then turn to face Margit Oldis d
      -> stirs 0.72, tone -0.50: suspicion 0.94, resolve 0.06
  MEMORY: I suspected this about Margit Oldis: Margit is shifting from concealing Kit's exit to managing how Aurel encounters the situation — clearing a path, n
      -> stirs 0.83, tone -0.55: suspicion 0.96
  MEMORY: Kit Sawyer came in. Kit Sawyer moved in Back Hall, too little of it to make out. I heard Kit Sawyer say: "Sir. I was at the mill last night -- I won't
      -> stirs 0.84, tone -0.60: suspicion 0.95
  MEMORY: I heard Kit Sawyer say "Sir. I was at the mill last night -- I won't lie about that. I pulled Wat out of the fire. But I never set it. I swear I never
      -> stirs 0.71, tone -0.47: suspicion 0.63, resolve 0.31, curiosity 0.05
  MOOD READ (spectrums | moods): playfulness -0.99, engagement +0.84, openness -0.63, pleasure -0.62, boldness +0.57 | resolve 0.99, suspicion 0.99, curiosity 0.94, longing 0.85, urgency 0.78
  mood after: suspicion +0.82, resolve +0.78, curiosity +0.63, playfulness -0.59, openness -0.53
  HANDED: now ['suspicion (You hear a muffled fragment from Margit Oldis: "...yours... ...)']
          beneath ['suspicion (Kit Sawyer came in. Kit Sawyer moved in Back Hall, too littl...)', 'resolve (I tried to close the case docket and return it to the satche...)']
          mood ['suspicion', 'resolve', 'curiosity', 'serious']
  -- Aurel Holt THEN:
     Does: Write in the case docket — recording Kit Sawyer's apology to Margit Oldis and the muffled fragment from Margit Oldis — pen moving in the careful hand
     Says (flat and precise — the warning register, not anger): "Kit Sawyer. That is recorded. Was the mill already burning when you arrived at the race?"
  -- AFTER, own acts:
     You Write in the case docket — recording Kit Sawyer's apology to Margit Oldis and the muffled fragment from Ma
        against 0.01, honours 0.99, regard +0.29, wanted else 0.71, eased/stoked -0.03
     You said: "Kit Sawyer. That is recorded. Was the mill already burning when you arrived at the race?"
        against 0.08, honours 0.95, regard +0.33, wanted else 0.81, eased/stoked -0.11
     You held back from: Address Margit's whispered interference — she has been told twice and is speaking again
        against 0.73, honours 0.66, regard -0.24, wanted else 0.80, eased/stoked +0.51
     felt: pride 0.29, shame 0.01, frustration 0.71, pride 0.30, shame 0.08, frustration 0.81, shame 0.73, frustration 0.80
     mood after: suspicion +0.84, resolve +0.80, curiosity +0.65, playfulness -0.60, longing +0.53  (stored surface: frustration (You said: "Kit Sawyer. That is recorded. Was the mill alread...))

====================================================================================================
TURN 2 >>> Kit turns to Miss Oldis, and his eyes are wet. "I'm sorry, miss. You lied for me, and it didn't even help."
--- narration ---
The pen lifts from the page and resumes its stroke — the first mark after the held pause, steady and deliberate, the nib tracking without his looking down.

Margit's right hand lifts an inch from her side toward Kit's shoulder, then settles back against her skirt. Her voice drops barely above a breath, lower than her usual measured register. "It was my choice, not yours. Answer him, Kit."

Holt's voice comes pitched low and even — quieter than his normal register, flat and precise, the warning tone and not anger. "Kit Sawyer. That is recorded. Was the mill already burning when you arrived at the race?"

## Anselm Ferro (turn 1) -- BEFORE THE CALL
  carried in: energy -0.60, tension -0.60, pleasure -0.30
  EVENT current:5:16: Luca Brandt stands looking from Varga on cot one to your hands.
      -> stirs 0.61: grief 0.29, suspicion 0.15, curiosity 0.10
  EVENT current:5:17: Luca Brandt lifts the letter from his chest and lays it on the cot rail.
      -> stirs 0.81: grief 0.43, curiosity 0.18, suspicion 0.11
  EVENT current:5:18: Luca Brandt says under their breath: "Corporal. Read it. Please. Just read it."
      -> stirs 0.81: compassion 0.28, grief 0.25, dread 0.16
  WORRY c0: the condition of the wounded man on the stretcher
      -> weighs 0.83, stirs 0.99: urgency 0.61, compassion 0.36
  WORRY c1: the dwindling medical supplies
      -> weighs 0.52, stirs 0.83: urgency 0.61, dread 0.20, fear 0.10
  WORRY c2: Pietro's empty bunk
      -> weighs 0.67, stirs 0.99: grief 0.79, regret 0.17
  WORRY c3: what Luca accused Varga of and whether the letter is proof
      -> weighs 0.59, stirs 0.81: suspicion 0.32, distress 0.27, curiosity 0.23
  MEMORY: You are in Infirmary. A low-ceilinged room cut into the rock, the walls rough-hewn and weeping moisture in the cold. Two cots line the walls under thi
      -> stirs 0.62, tone -0.54: dread 0.33, urgency 0.19, compassion 0.16
  MEMORY: I saw Luca Brandt step closer to the basin stand. I heard Luca Brandt say: "Corporal. They're burying Pietro at eight -- the captain says the whole ga
      -> stirs 0.87, tone -0.67: grief 0.90, tenderness 0.05
  MEMORY: I tried to look down at my own empty hands. Then I said 'The iodine stock needs—'. Then I said 'Right.' Then I tried to turn toward the infirmary door
      -> stirs 0.72, tone -0.57: grief 0.70, regret 0.09, numbness 0.09
  MEMORY: Luca Brandt came in. I heard Luca Brandt say: "He saved me a heel of bread every night I was on the late watch," I heard Luca Brandt say: "Every singl
      -> stirs 0.82, tone -0.54: grief 0.83, moved 0.11
  MEMORY: I heard Luca Brandt say: "Corporal -- the north patrol's back early. They're carrying someone. I think they walked into something at the saddle." I sa
      -> stirs 0.74, tone -0.64: urgency 0.96
  MEMORY: Luca Brandt came in. I saw Luca Brandt hold the lamp steady over the cot. I heard Luca Brandt say something I could not make out: ...Brenner... waitin
      -> stirs 0.64, tone -0.56: urgency 0.84, curiosity 0.07, dread 0.05
  MEMORY: I said "Two on a stretcher, one walking, favouring his left. That's all I have. Don't know what they hit yet." Then I tried to walk through the yard d
      -> stirs 0.64, tone -0.53: urgency 0.97
  MEMORY: I suspected this about Luca Brandt: Luca appears to already be in the infirmary preparing — holding the lamp over the cot.
      -> stirs 0.41, tone -0.35: suspicion 0.43, urgency 0.11, moved 0.08
  MOOD READ (spectrums | moods): playfulness -0.97, engagement +0.66, pleasure -0.63, energy -0.57, sociability -0.47 | compassion 0.98, resolve 0.93, protectiveness 0.89, urgency 0.87, grief 0.86
  mood after: energy -0.48, pleasure -0.43, grief +0.38, urgency +0.35, compassion +0.31
  HANDED: now ['grief (Luca Brandt lifts the letter from his chest and lays it on t...)', 'compassion (Luca Brandt says under their breath: "Corporal. Read it. Ple...)']
          beneath ['grief (I saw Luca Brandt step closer to the basin stand. I heard Lu...)', 'urgency (I heard Luca Brandt say: "Corporal -- the north patrol\'s bac...)']
          mood ['drained', 'unpleasant', 'grief', 'urgency']
  -- Anselm Ferro THEN:
     Does: Continue easing the fragment free with the forceps — left hand pressing wound edges apart, feeling the metal's edges as it shifts, keeping eyes fixed on the wound field and not on the cot rail
     Says (flat, clinical — a refusal that is not a dismissal): "I see it, Brandt. Not now."
  -- AFTER, own acts:
     You Continue easing the fragment free with the forceps — left hand pressing wound edges apart, feeling the met
        against 0.14, honours 0.96, regard +0.33, wanted else 0.75, eased/stoked -0.28
     You said: "I see it, Brandt. Not now."
        against 0.18, honours 0.89, regard +0.16, wanted else 0.76, eased/stoked +0.04
     You held back from: Answer Luca — the letter is on the rail now, he defied an order to bring it to me
        against 0.26, honours 0.81, regard +0.07, wanted else 0.63, eased/stoked +0.31
     felt: pride 0.28, shame 0.14, frustration 0.75, pride 0.13, shame 0.18, frustration 0.76, pride 0.05, shame 0.26, frustration 0.63
     mood after: energy -0.40, pleasure -0.39, grief +0.38, urgency +0.36, compassion +0.32  (stored surface: frustration (You said: "I see it, Brandt. Not now."))

## Emil Varga (turn 1) -- BEFORE THE CALL
  carried in: pleasure -0.60
  EVENT current:3:14: Luca Brandt stands looking from you on cot one to Ferro's hands.
      -> stirs 0.82: suspicion 0.40, fear 0.17, dread 0.17
  EVENT current:3:micro:0:5:0: Both hands remain on the patient's left flank — forceps grip something inside the wound, left hand presses tissue apart, gaze holds on the wound.
      -> stirs 0.58: distress 0.20, urgency 0.14, dread 0.12
  EVENT current:3:15: Luca Brandt lifts the letter from his chest and lays it on the cot rail.
      -> stirs 0.93: dread 0.59, fears_confirmed 0.13, fear 0.10
  EVENT current:3:micro:0:5:1: Anselm Ferro says: "I see it, Brandt. Not now."
      -> stirs 0.86: relief 0.27, dread 0.26, fears_confirmed 0.13
  EVENT current:3:16: Luca Brandt says under their breath: "Corporal. Read it. Please. Just read it."
      -> stirs 0.97: dread 0.60, suspicion 0.12, fears_confirmed 0.11
  WORRY c0: Luca Brandt is defying command authority and appealing directly to Anselm
      -> weighs 0.91, stirs 0.95: dread 0.30, fears_confirmed 0.15, suspicion 0.15
  WORRY c1: Anselm must not engage with the letter or Luca's accusation
      -> weighs 0.94, stirs 0.94: dread 0.44, resolve 0.13, fear 0.10
  WORRY c2: What is in the letter Luca is holding
      -> weighs 0.93, stirs 0.98: dread 0.48, fear 0.18, fears_confirmed 0.13
  WORRY c3: North patrol casualties — was the western ridge route compromised
      -> weighs 0.92, stirs 0.97: fears_confirmed 0.60, remorse 0.10, guilt 0.09
  MEMORY: You are in Command Post. A stone chamber barely wider than the table that dominates it. The map of the pass is pinned to the table's surface, patrol r
      -> stirs 0.84, tone -0.53: guilt 0.39, dread 0.18, regret 0.11
  MEMORY: I tried to pull the unfinished letter closer under the lantern light and read what he wrote last night. Then I tried to pick up the pencil and continu
      -> stirs 0.98, tone -0.76: grief 0.89, guilt 0.06
  MEMORY: I tried to look down at the patrol map and study the routes — the crossed-out lines where men died, the circled ones he recognizes as his own work. Th
      -> stirs 0.94, tone -0.68: guilt 0.59, regret 0.19, haunted 0.09
  MEMORY: Luca Brandt came in. Anselm Ferro came in. I heard Luca Brandt say: "He saved me a heel of bread every night I was on the late watch," I heard Luca Br
      -> stirs 0.85, tone -0.56: guilt 0.43, suspicion 0.16, regret 0.08
  MEMORY: I heard Luca Brandt say: "Corporal -- the north patrol's back early. They're carrying someone. I think they walked into something at the saddle." I sa
      -> stirs 0.89, tone -0.67: dread 0.49, suspicion 0.30, urgency 0.16
  MEMORY: I heard Luca Brandt say "Corporal -- the north patrol's back early. They're carrying someone. I think they walked into something at the saddle." to An
      -> stirs 0.89, tone -0.69: dread 0.50, suspicion 0.30, urgency 0.12
  MEMORY: I saw Luca Brandt hold the lamp steady over the cot. I saw Luca Brandt avoid looking at the wound. I saw Luca Brandt swallow. I saw an indistinct figu
      -> stirs 0.79, tone -0.56: suspicion 0.49, dread 0.24, urgency 0.11
  MEMORY: I heard Anselm Ferro say "Two on a stretcher, one walking, favouring his left. That's all I have. Don't know what they hit yet." to me
      -> stirs 0.79, tone -0.58: dread 0.47, urgency 0.24, suspicion 0.16
  MOOD READ (spectrums | moods): playfulness -0.99, pleasure -0.78, engagement +0.69, openness -0.67, tension +0.67 | guilt 0.97, regret 0.97, protectiveness 0.96, dread 0.96, longing 0.91
  mood after: pleasure -0.63, dread +0.42, guilt +0.36, suspicion +0.35, grief +0.29
  HANDED: now ['dread (Luca Brandt says under their breath: "Corporal. Read it. Ple...)', "suspicion (Luca Brandt stands looking from you on cot one to Ferro's ha...)"]
          beneath ['grief (I tried to pull the unfinished letter closer under the lante...)', 'guilt (I tried to look down at the patrol map and study the routes ...)']
          mood ['unpleasant', 'dread', 'guilt', 'suspicion']
  -- Emil Varga THEN:
     Does: Reach to the cot rail and take the letter, closing it without reading the contents, and tuck it inside his greatcoat
     Says (measured, brief — a captain handing off a station): "You've got your light, Anselm. I'll send someone to assist you."
     Says (flat, final — quiet where it should carry, the volume calibrated to Luca's ears): "Brandt. Walk out that door. Now."
     Does: Turn toward the corridor door to leave, expecting Luca to precede him
  -- AFTER, own acts:
     You Reach to the cot rail and take the letter, closing it without reading the contents, and tuck it inside his
        against 0.24, honours 0.82, regard -0.16, wanted else 0.71, eased/stoked +0.18
     You said: "You've got your light, Anselm. I'll send someone to assist you."
        against 0.08, honours 0.81, regard +0.02, wanted else 0.71, eased/stoked -0.11
     You said: "Brandt. Walk out that door. Now."
        against 0.11, honours 0.91, regard -0.02, wanted else 0.59, eased/stoked -0.14
     You Turn toward the corridor door to leave, expecting Luca to precede him
        against 0.23, honours 0.70, regard -0.16, wanted else 0.59, eased/stoked +0.18
     You held back from: Assess what Anselm understood from 'I see it' — did he read the contents or just see a let
        against 0.32, honours 0.74, regard -0.28, wanted else 0.74, eased/stoked +0.56
     felt: shame 0.24, frustration 0.71, pride 0.02, shame 0.08, frustration 0.71, shame 0.11, frustration 0.59, shame 0.23, frustration 0.59, shame 0.32, frustration 0.74
     mood after: pleasure -0.57, dread +0.43, guilt +0.37, suspicion +0.36, self_regard -0.31  (stored surface: frustration (You held back from: Assess what Anselm understood from 'I se...))

====================================================================================================
TURN 1 >>> Luca doesn't go. He looks at the captain, then at the medic's bloody hands, and lays the letter on the cot rail where the corporal can see the seal and the handwriting without touching it. "Corporal. Read it. Please. Just read it."
--- narration ---
Anselm's voice comes without his head lifting — under his breath, flat, clinical. "I see it, Brandt. Not now." His gaze holds on the wound. It does not track to the rail where the letter lies. His left hand presses the wound edges a fraction harder than the extraction requires.

Emil reaches down and takes the letter from the rail. He does not unfold it. He does not glance at the page — the page he said he would read every word of — and folds it shut between his fingers and slides it inside his greatcoat, against his tunic. His breath holds shallow through the nose while the paper disappears into the coat. One controlled exhale after it is tucked, and then his voice drops low and final. "You've got your light, Anselm. I'll send someone to assist you. Brandt. Walk out that door. Now."

He turns toward the infirmary door, his body angling past the cot and the basin stand, and the corridor'

## Anselm Ferro (turn 2) -- BEFORE THE CALL
  carried in: energy -0.40, pleasure -0.39, grief +0.38, urgency +0.36, compassion +0.32
  EVENT current:5:14: Luca Brandt stands at the threshold watching in silence.
      -> stirs 0.56: grief 0.35, urgency 0.23, curiosity 0.11
  WORRY c0: the condition of the wounded man on the stretcher
      -> weighs 0.94, stirs 0.99: urgency 0.67, compassion 0.32
  WORRY c1: the dwindling medical supplies
      -> weighs 0.57, stirs 0.92: urgency 0.74, dread 0.15, distress 0.07
  WORRY c2: Pietro's empty bunk
      -> weighs 0.69, stirs 0.99: grief 0.93, regret 0.06
  WORRY c3: what Luca accused Varga of and whether the letter is proof
      -> weighs 0.45, stirs 0.70: distress 0.31, suspicion 0.29, curiosity 0.18
  MEMORY: You are in Infirmary. A low-ceilinged room cut into the rock, the walls rough-hewn and weeping moisture in the cold. Two cots line the walls under thi
      -> stirs 0.71, tone -0.60: urgency 0.42, compassion 0.20, dread 0.15
  MEMORY: I saw Luca Brandt step closer to the basin stand. I heard Luca Brandt say: "Corporal. They're burying Pietro at eight -- the captain says the whole ga
      -> stirs 0.90, tone -0.67: grief 0.93
  MEMORY: Luca Brandt came in. I heard Luca Brandt say: "He saved me a heel of bread every night I was on the late watch," I heard Luca Brandt say: "Every singl
      -> stirs 0.84, tone -0.54: grief 0.84, moved 0.13
  MEMORY: I heard Luca Brandt say: "Corporal -- the north patrol's back early. They're carrying someone. I think they walked into something at the saddle." I sa
      -> stirs 0.81, tone -0.68: urgency 1.00
  MEMORY: I suspected this about Luca Brandt: Luca brings urgent tactical-medical information directly and immediately, understanding that Anselm needs to know 
      -> stirs 0.63, tone +0.11: urgency 0.68, gratitude 0.19, admiration 0.12
  MEMORY: Luca Brandt came in. I saw Luca Brandt hold the lamp steady over the cot. I heard Luca Brandt say something I could not make out: ...Brenner... waitin
      -> stirs 0.75, tone -0.57: urgency 0.97
  MEMORY: I said "Two on a stretcher, one walking, favouring his left. That's all I have. Don't know what they hit yet." Then I tried to walk through the yard d
      -> stirs 0.68, tone -0.55: urgency 1.00
  MEMORY: I suspected this about Luca Brandt: Luca appears to already be in the infirmary preparing — holding the lamp over the cot.
      -> stirs 0.47, tone +0.05: urgency 0.55, gratitude 0.17, moved 0.10
  MOOD READ (spectrums | moods): playfulness -0.97, engagement +0.78, pleasure -0.65, tension +0.47, boldness +0.47 | compassion 1.00, urgency 0.99, resolve 0.97, grief 0.94, protectiveness 0.93
  mood after: urgency +0.62, grief +0.60, compassion +0.50, sadness +0.47, pleasure -0.46
  HANDED: now ['grief (Luca Brandt stands at the threshold watching in silence.)', 'urgency (Luca Brandt stands at the threshold watching in silence.)']
          beneath ['grief (I saw Luca Brandt step closer to the basin stand. I heard Lu...)', 'urgency (I heard Luca Brandt say: "Corporal -- the north patrol\'s bac...)']
          mood ['urgency', 'grief', 'compassion', 'sadness']
  -- Anselm Ferro THEN:
     Says (low, clinical, even): "I heard you, Brandt. Go."
     Says (lower, slower, the words spaced deliberately): "I'll find you when he's closed."
     Does: Continue easing the fragment free with the forceps — draw the shard slowly out of the wound, left hand pressing the edges apart to keep the field open, feeling the metal's grip on the forceps as it shifts through the tissue, keeping eyes fixed on the wou
  -- AFTER, own acts:
     You said: "I heard you, Brandt. Go."
        against 0.16, honours 0.84, regard +0.11, wanted else 0.56, eased/stoked +0.27
     You said: "I'll find you when he's closed."
        against 0.11, honours 0.85, regard +0.13, wanted else 0.34, eased/stoked +0.08
     You Continue easing the fragment free with the forceps — draw the shard slowly out of the wound, left hand pre
        against 0.09, honours 0.98, regard +0.35, wanted else 0.54, eased/stoked +0.02
     You held back from: Give Luca enough to go on without lifting hands from the wound
        against 0.35, honours 0.89, regard +0.05, wanted else 0.56, eased/stoked +0.34
     felt: pride 0.10, shame 0.16, frustration 0.56, pride 0.12, shame 0.11, frustration 0.34, pride 0.31, shame 0.09, frustration 0.54, pride 0.03, shame 0.35, frustration 0.56
     mood after: urgency +0.64, grief +0.62, compassion +0.52, sadness +0.49, playfulness -0.44  (stored surface: frustration (You said: "I heard you, Brandt. Go."))

## Emil Varga (turn 2) -- BEFORE THE CALL
  carried in: pleasure -0.57, dread +0.43, guilt +0.37, suspicion +0.36, self_regard -0.31
  EVENT current:3:micro:0:5:0: Anselm Ferro says: "I heard you, Brandt. Go. I'll find you when he's closed."
      -> stirs 0.71: dread 0.28, suspicion 0.23, guilt 0.11
  EVENT current:3:12: Anselm Ferro works the surgical forceps toward the corroded shard.
      -> stirs 0.65: dread 0.33, compassion 0.15, distress 0.11
  EVENT current:3:micro:0:5:1: His right hand draws the forceps upward in a slow, controlled pull while his left hand holds the wound edges apart, knuckles whitening slightly against the flesh.
      -> stirs 0.66: dread 0.25, compassion 0.23, distress 0.21
  EVENT current:3:13: Luca Brandt stands at the threshold watching in silence.
      -> stirs 0.65: suspicion 0.74, dread 0.07, fears_confirmed 0.06
  WORRY c0: The letter is on the cot rail with patrol times in his own hand and a foreign seal — Anselm acknowledged seeing it
      -> weighs 0.90, stirs 0.97: dread 0.40, suspicion 0.20, fears_confirmed 0.20
  WORRY c1: Anselm said 'not now' — he intends to read it later
      -> weighs 0.81, stirs 0.86: dread 0.66, suspicion 0.10, fear 0.09
  WORRY c2: Luca defied a direct order and appealed to Anselm again
      -> weighs 0.71, stirs 0.87: suspicion 0.36, anger 0.21, dread 0.19
  WORRY c3: Whether Anselm read the contents or only saw the letter's existence
      -> weighs 0.87, stirs 0.98: dread 0.48, fear 0.26, suspicion 0.12
  MEMORY: You are in Command Post. A stone chamber barely wider than the table that dominates it. The map of the pass is pinned to the table's surface, patrol r
      -> stirs 0.81, tone -0.54: guilt 0.44, dread 0.35, mastery 0.06
  MEMORY: I tried to pull the unfinished letter closer under the lantern light and read what he wrote last night. Then I tried to pick up the pencil and continu
      -> stirs 0.98, tone -0.81: grief 0.90, guilt 0.07
  MEMORY: I tried to look down at the patrol map and study the routes — the crossed-out lines where men died, the circled ones he recognizes as his own work. Th
      -> stirs 0.92, tone -0.67: guilt 0.83, grief 0.05, regret 0.05
  MEMORY: Luca Brandt came in. Anselm Ferro came in. I heard Luca Brandt say: "He saved me a heel of bread every night I was on the late watch," I heard Luca Br
      -> stirs 0.84, tone -0.54: guilt 0.55, moved 0.15, suspicion 0.08
  MEMORY: I heard Luca Brandt say: "Corporal -- the north patrol's back early. They're carrying someone. I think they walked into something at the saddle." I sa
      -> stirs 0.79, tone -0.60: urgency 0.46, dread 0.33, suspicion 0.17
  MEMORY: I saw Luca Brandt hold the lamp steady over the cot. I saw Luca Brandt avoid looking at the wound. I saw Luca Brandt swallow. I saw an indistinct figu
      -> stirs 0.78, tone -0.58: suspicion 0.26, dread 0.23, guilt 0.17
  MEMORY: I heard Anselm Ferro say "Two on a stretcher, one walking, favouring his left. That's all I have. Don't know what they hit yet." to me
      -> stirs 0.75, tone -0.62: urgency 0.49, dread 0.27, guilt 0.12
  MEMORY: I heard a voice say: "Two on the stretchers, Corporal—one's out cold, the other's breathing but bad. The walking man took something in the shoulder, l
      -> stirs 0.78, tone -0.58: urgency 0.36, dread 0.22, guilt 0.18
  MOOD READ (spectrums | moods): playfulness -0.99, pleasure -0.85, engagement +0.61, tension +0.54, energy -0.53 | guilt 0.98, protectiveness 0.97, regret 0.96, longing 0.95, dread 0.92
  mood after: pleasure -0.63, dread +0.63, guilt +0.61, suspicion +0.56, grief +0.51
  HANDED: now ['suspicion (Luca Brandt stands at the threshold watching in silence.)']
          beneath ['grief (I tried to pull the unfinished letter closer under the lante...)', 'guilt (I tried to look down at the patrol map and study the routes ...)']
          mood ['unpleasant', 'dread', 'guilt', 'suspicion']
  -- Emil Varga THEN:
     Does: Walk through the infirmary door into the Main Corridor, passing Luca at the threshold without stopping or looking back at Anselm
  -- AFTER, own acts:
     You Walk through the infirmary door into the Main Corridor, passing Luca at the threshold without stopping or 
        against 0.38, honours 0.44, regard -0.45, wanted else 0.87, eased/stoked +0.52
     You held back from: Assess what Anselm understood from 'I see it' — did he read the contents or just see a let
        against 0.37, honours 0.69, regard -0.40, wanted else 0.79, eased/stoked +0.55
     felt: shame 0.46, frustration 0.87, shame 0.41, frustration 0.79
     mood after: dread +0.70, guilt +0.64, suspicion +0.62, pleasure -0.58, grief +0.56  (stored surface: frustration (You Walk through the infirmary door into the Main Corridor, ...))

====================================================================================================
TURN 2 >>> Luca steps back until his shoulders touch the doorframe, so that he is standing in the only way out, and waits for whichever of them speaks first.
--- narration ---
He works the forceps toward the corroded shard — steel jaws finding the edge, a faint grating of metal on decayed steel — and Anselm's hand closes over the instrument, taking it without looking up. Luca steps back to the threshold and watches.

Across the room, Anselm works the forceps toward the shard, hunched close over the wound, his body curved under the low ceiling. The lamp holds its dim pool on the patient's flank. The muscles along his jaw tighten — a slow clench that holds through both sentences and releases only after his mouth closes. "I heard you, Brandt. Go. I'll find you when he's closed." The first comes level, clinical. The second falls quieter, aimed past the captain's position toward the doorway.

Emil rises. His right hand pulls the greatcoat closed across his chest — the motion reads as bracing against the corridor cold, and it shields the letter's outline from view. 

## Wren Halloway (turn 1) -- BEFORE THE CALL
  carried in: energy +0.30, tension +0.30
  EVENT current:4:18: Jonah Pell opens his fist and places the folded slip of card into your palm.
      -> stirs 0.93: anticipation 0.21, resolve 0.18, dread 0.16
  EVENT current:4:19: Jonah Pell closes her fingers over the card with his own fingers.
      -> stirs 0.92: dread 0.25, resolve 0.17, guilt 0.13
  WORRY c0: the card in Jonah's coat — still unseen, still unshown, four times asked now
      -> weighs 0.74, stirs 0.95: curiosity 0.35, suspicion 0.13, guilt 0.13
  WORRY c1: the unopened acceptance letter in the satchel
      -> weighs 0.83, stirs 0.99: anticipation 0.42, dread 0.20, resolve 0.15
  WORRY c2: Jonah saying lighthouse and remember on the breakwater where they carved their names
      -> weighs 0.79, stirs 0.99: haunted 0.33, guilt 0.33, dread 0.12
  WORRY c3: Friday's coach and the promise that won't fit on it
      -> weighs 0.88, stirs 0.99: guilt 0.50, resolve 0.21, dread 0.11
  MEMORY: You are in the harbour wall. A long stone breakwater running east from the quay to the lighthouse point, wide enough for two men to walk abreast. The 
      -> stirs 0.92, tone -0.17: urgency 0.24, guilt 0.21, resolve 0.18
  MEMORY: Jonah Pell came in. I saw Jonah Pell boot hanging over the edge. I heard Jonah Pell say: "Three days," I heard Jonah Pell say: "Your father reckons th
      -> stirs 0.93, tone -0.30: urgency 0.37, guilt 0.20, resolve 0.16
  MEMORY: I heard a voice say "Three days and the current's still ebbing — she'll clear the Point easy if she goes within the hour." to Jonah Pell
      -> stirs 0.79, tone -0.13: urgency 0.83, guilt 0.06, resolve 0.05
  MEMORY: I tried to slide the unopened letter into the canvas satchel without looking down, pulling the strap closed after. Then I said "Nearly. That skiff's c
      -> stirs 0.91, tone -0.54: guilt 0.32, urgency 0.30, resolve 0.18
  MEMORY: I saw Jonah Pell squint at the channel toward the incoming boat. I heard Jonah Pell say: "Come out in the Tern with me this afternoon," I heard Jonah 
      -> stirs 0.85, tone -0.19: guilt 0.22, nostalgia 0.17, resolve 0.13
  MEMORY: I tried to move her hand from the satchel strap at her hip to the iron rail, fingers closing on salt-pitted metal where names are carved. Then I said 
      -> stirs 0.90, tone -0.35: guilt 0.34, resolve 0.19, urgency 0.16
  MEMORY: I saw Jonah Pell run his thumb along the carving on the iron rail. I heard Jonah Pell say: "Fourteen, we were. You remember what we promised up here?"
      -> stirs 0.98, tone -0.58: guilt 0.45, resolve 0.16, dread 0.13
  MEMORY: I heard Aldo Halloway say "The Tern draws three foot. Shelf's at two and falling. You go now, you've got the tide with you to the Point. Coming back's
      -> stirs 0.81, tone -0.51: urgency 0.62, resolve 0.13, dread 0.10
  MOOD READ (spectrums | moods): playfulness -0.92, engagement +0.60, tension +0.52, boldness +0.47, energy +0.43 | resolve 0.95, urgency 0.92, haunted 0.86, guilt 0.79, anticipation 0.76
  mood after: tension +0.38, urgency +0.37, energy +0.36, resolve +0.35, guilt +0.33
  HANDED: now ['dread (Jonah Pell closes her fingers over the card with his own fin...)', 'anticipation (Jonah Pell opens his fist and places the folded slip of card...)', 'resolve (Jonah Pell opens his fist and places the folded slip of card...)']
          beneath ['urgency (I heard a voice say "Three days and the current\'s still ebbi...)', 'guilt (I saw Jonah Pell run his thumb along the carving on the iron...)']
          mood ['tense', 'urgency', 'energized', 'resolve']
  -- Wren Halloway THEN:
     Does: Pull her hand back from Jonah's, drawing the folded card with it — breaking the contact of his fingers on hers
     Does: Unfold the card with both hands, cold fingers working the creases open against the wind, angling her body to shield the paper from the gale
  -- AFTER, own acts:
     You Pull her hand back from Jonah's, drawing the folded card with it — breaking the contact of his fingers on 
        against 0.15, honours 0.79, regard +0.08, wanted else 0.60, eased/stoked +0.40
     You Unfold the card with both hands, cold fingers working the creases open against the wind, angling her body 
        against 0.09, honours 0.72, regard +0.09, wanted else 0.72, eased/stoked +0.70
     You held back from: Look at Jonah's face before she reads it — his expression might tell her what the card say
        against 0.38, honours 0.75, regard +0.17, wanted else 0.59, eased/stoked +0.33
     felt: pride 0.07, shame 0.15, frustration 0.60, pride 0.09, shame 0.09, frustration 0.72, pride 0.11, shame 0.38, frustration 0.59
     mood after: tension +0.42, urgency +0.40, resolve +0.38, guilt +0.37, energy +0.36  (stored surface: frustration (You Unfold the card with both hands, cold fingers working th...))

## Aldo Halloway (turn 1) -- BEFORE THE CALL
  carried in: energy -0.40, tension -0.40
  EVENT current:6:micro:0:4:0: Wren Halloway pulls her hand back, the card coming with it, his fingers sliding off hers.
      -> stirs 0.53: dread 0.16, disappointment 0.15, fears_confirmed 0.11 (nothing much 0.12)
  EVENT current:6:micro:0:4:1: Both hands come together over the card, pressing the folds open, her body turning slightly to block the wind.
      -> stirs 0.35: protectiveness 0.21, dread 0.14, curiosity 0.07 (nothing much 0.15)
  EVENT current:6:12: Jonah Pell closes her fingers over the card with his own fingers.
      -> stirs 0.57: suspicion 0.27, jealousy 0.24, protectiveness 0.13
  MEMORY: You are in the harbourmaster's shed. A small clapboard shed at the head of the quay, smelling of tar, wet wool, and cold tea. Tide tables and shipping
      -> stirs 0.54, tone +0.09: protectiveness 0.54, resolve 0.19, urgency 0.11
  MEMORY: I heard Jonah Pell say something I could not make out: ...Three... days... I heard Jonah Pell say something I could not make out: ...reckons... weathe
      -> stirs 0.62, tone -0.48: urgency 0.31, suspicion 0.27, protectiveness 0.17
  MEMORY: I heard Wren Halloway say "Nearly. That skiff's close-hauled on the entrance. Wind's backed a point since dawn."
      -> stirs 0.57, tone -0.40: urgency 0.56, protectiveness 0.30, admiration 0.08
  MEMORY: I tried to walk out through the shed door to the quay wall by the bollards, looking toward the harbour entrance at the incoming skiff. Then I tried to
      -> stirs 0.56, tone -0.36: suspicion 0.35, protectiveness 0.34, urgency 0.25
  MEMORY: I concluded this about Wren Halloway: She reads the wind and the harbour entrance as well as he does.
      -> stirs 0.39, tone +0.21: admiration 0.75, protectiveness 0.12
  MEMORY: I concluded that An unfamiliar person standing on the quay with a clear view of the breakwater.
      -> stirs 0.66, tone -0.51: suspicion 0.99
  MEMORY: I heard Wren Halloway say: "Wind'll hold till mid-afternoon. We could make the point and back before she turns." I was standing on the ground beside t
      -> stirs 0.52, tone -0.14: urgency 0.39, protectiveness 0.34, admiration 0.15
  MEMORY: I heard Wren Halloway say "Wind'll hold till mid-afternoon. We could make the point and back before she turns."
      -> stirs 0.49, tone -0.07: urgency 0.40, protectiveness 0.36, admiration 0.12
  MOOD READ (spectrums | moods): playfulness -0.84, boldness +0.60, openness -0.58, engagement +0.57, sociability -0.56 | resolve 0.94, protectiveness 0.92, urgency 0.68, suspicion 0.57, mastery 0.43
  mood after: energy -0.34, protectiveness +0.33, urgency +0.26
  HANDED: now ['suspicion (Jonah Pell closes her fingers over the card with his own fin...)', 'jealousy (Jonah Pell closes her fingers over the card with his own fin...)', 'dread (Wren Halloway pulls her hand back, the card coming with it, ...)']
          beneath ['suspicion (I concluded that An unfamiliar person standing on the quay w...)']
          mood ['drained', 'protectiveness', 'urgency']
  -- Aldo Halloway THEN:
     Does: Walk further along the breakwater toward Wren and Jonah, closing the distance to where the card might be legible or their words audible
  -- AFTER, own acts:
     You Walk further along the breakwater toward Wren and Jonah, closing the distance to where the card might be l
        against 0.13, honours 0.78, regard +0.11, wanted else 0.63, eased/stoked +0.13
     You held back from: Stay back and let Wren handle this — she demanded the card herself, she doesn't need me ho
        against 0.57, honours 0.49, regard -0.10, wanted else 0.73, eased/stoked +0.42
     felt: pride 0.10, shame 0.13, frustration 0.63, shame 0.57, frustration 0.73
     mood after: protectiveness +0.35, energy -0.32, urgency +0.27, resolve +0.26, suspicion +0.26  (stored surface: frustration (You held back from: Stay back and let Wren handle this — she...))

====================================================================================================
TURN 1 >>> Jonah looks at her open hand for a long moment. Then he opens his fist and puts the crushed card into her palm, and closes her fingers over it with his own.
--- narration ---
Wren pulls her hand back and the card goes with it — his fingers sliding away from hers, the last warmth of the crushed paper transferring between their skins in the instant before contact breaks. She angles her shoulder into the wind to shield the ticket, both hands gripping the corners, and her thumbs press the card flat against the gust. Harder than the paper needs. The cheap stock has gone soft from his grip, the crease deep-set, and she works it flat the way she'd work a chart flat on a table — deliberate, unhurried, the chase ended and the reading begun. Everything else peripheral. The edge snaps taut in a brief lull and her fingers tighten on it.

Aldo is coming. His boots find the wet breakwater stone with the patience of a man who has stood in worse, hands open at his sides, not reaching for anything, not gripping the rail. Six paces and closing. His jaw sets tighter with each s

## Wren Halloway (turn 2) -- BEFORE THE CALL
  carried in: tension +0.42, urgency +0.40, resolve +0.38, guilt +0.37, energy +0.36
  EVENT current:4:15: Jonah Pell says: "Go on, then. The coach won't wait. I'll write. I'll look after the Tern."
      -> stirs 0.95: guilt 0.70, resolve 0.11, moved 0.08
  EVENT current:4:16: Jonah Pell steps back from you along the harbour wall.
      -> stirs 0.90: guilt 0.53, resolve 0.26, urgency 0.08
  WORRY c0: the card in her hand — unfolding it now
      -> weighs 0.69, stirs 0.95: guilt 0.25, resolve 0.23, dread 0.16
  WORRY c1: the unopened acceptance letter in the satchel
      -> weighs 0.86, stirs 0.99: urgency 0.28, guilt 0.22, resolve 0.18
  WORRY c2: Friday's coach and the promise that won't fit on it
      -> weighs 0.93, stirs 0.99: guilt 0.70, urgency 0.15, resolve 0.12
  MEMORY: You are in the harbour wall. A long stone breakwater running east from the quay to the lighthouse point, wide enough for two men to walk abreast. The 
      -> stirs 0.86, tone +0.02: guilt 0.33, urgency 0.26, resolve 0.20
  MEMORY: Jonah Pell came in. I saw Jonah Pell boot hanging over the edge. I heard Jonah Pell say: "Three days," I heard Jonah Pell say: "Your father reckons th
      -> stirs 0.90, tone -0.41: guilt 0.37, urgency 0.35, resolve 0.15
  MEMORY: I tried to slide the unopened letter into the canvas satchel without looking down, pulling the strap closed after. Then I said "Nearly. That skiff's c
      -> stirs 0.88, tone -0.53: urgency 0.42, guilt 0.35, resolve 0.19
  MEMORY: I saw Jonah Pell squint at the channel toward the incoming boat. I heard Jonah Pell say: "Come out in the Tern with me this afternoon," I heard Jonah 
      -> stirs 0.83, tone -0.29: guilt 0.43, nostalgia 0.15, resolve 0.12
  MEMORY: I tried to move her hand from the satchel strap at her hip to the iron rail, fingers closing on salt-pitted metal where names are carved. Then I said 
      -> stirs 0.87, tone -0.42: guilt 0.37, resolve 0.24, urgency 0.21
  MEMORY: I saw Jonah Pell run his thumb along the carving on the iron rail. I heard Jonah Pell say: "Fourteen, we were. You remember what we promised up here?"
      -> stirs 0.98, tone -0.57: guilt 0.76, resolve 0.07
  MEMORY: I heard Aldo Halloway say "The Tern draws three foot. Shelf's at two and falling. You go now, you've got the tide with you to the Point. Coming back's
      -> stirs 0.80, tone -0.53: urgency 0.61, guilt 0.17, dread 0.11
  MEMORY: I heard Aldo Halloway say "Take the long way round. South channel. Adds an hour but the bottom's sound."
      -> stirs 0.63, tone -0.25: urgency 0.27, guilt 0.27, resolve 0.26
  MOOD READ (spectrums | moods): playfulness -0.94, engagement +0.61, boldness +0.47, tension +0.47, pleasure -0.45 | resolve 0.98, urgency 0.95, guilt 0.90, haunted 0.85, regret 0.62
  mood after: guilt +0.61, urgency +0.61, resolve +0.60, playfulness -0.42, tension +0.42
  HANDED: now ['guilt (Jonah Pell says: "Go on, then. The coach won\'t wait. I\'ll wr...)']
          beneath ['guilt (I saw Jonah Pell run his thumb along the carving on the iron...)', 'urgency (I heard Aldo Halloway say "The Tern draws three foot. Shelf\'...)']
          mood ['guilt', 'urgency', 'resolve', 'serious']
  -- Wren Halloway THEN:
     Does: Look down at the unfolded card in her hands and read what's written on it — eyes scanning the text, body angled to shield the paper from the gale
  -- AFTER, own acts:
     You Look down at the unfolded card in her hands and read what's written on it — eyes scanning the text, body a
        against 0.08, honours 0.58, regard -0.42, wanted else 0.83, eased/stoked +0.71
     You held back from: Look up at Jonah — see what his face is doing now that he's stepped back
        against 0.44, honours 0.57, regard -0.33, wanted else 0.79, eased/stoked +0.55
     felt: shame 0.41, frustration 0.83, shame 0.44, frustration 0.79
     mood after: urgency +0.69, resolve +0.68, guilt +0.65, playfulness -0.48, haunted +0.47  (stored surface: frustration (You Look down at the unfolded card in her hands and read wha...))

## Aldo Halloway (turn 2) -- BEFORE THE CALL
  carried in: protectiveness +0.35, energy -0.32, urgency +0.27, resolve +0.26, suspicion +0.26
  EVENT current:6:12: Jonah Pell says something you cannot make out: ...coach... won't... write...
      -> stirs 0.62: curiosity 0.33, urgency 0.30, suspicion 0.20
  EVENT current:6:micro:0:4:0: Her chin drops and her eyes fix on the unfolded card in her hands; her shoulders round inward over the paper, sheltering it from the wind with her body.
      -> stirs 0.85: protectiveness 0.33, dread 0.26, fears_confirmed 0.24
  WORRY c0: What is the card Jonah has been carrying, and what does it mean for Friday's coach?
      -> weighs 0.59, stirs 0.65: curiosity 0.30, suspicion 0.25, dread 0.18
  WORRY c1: Will Wren and Jonah sail the Tern to the Point today, and will they take the south channel?
      -> weighs 0.79, stirs 0.92: protectiveness 0.72, urgency 0.13, curiosity 0.05
  MEMORY: You are in the harbourmaster's shed. A small clapboard shed at the head of the quay, smelling of tar, wet wool, and cold tea. Tide tables and shipping
      -> stirs 0.63, tone +0.00: protectiveness 0.59, resolve 0.27, urgency 0.08
  MEMORY: I heard Jonah Pell say something I could not make out: ...Three... days... I heard Jonah Pell say something I could not make out: ...reckons... weathe
      -> stirs 0.69, tone -0.50: urgency 0.36, protectiveness 0.22, curiosity 0.18
  MEMORY: I heard Wren Halloway say "Nearly. That skiff's close-hauled on the entrance. Wind's backed a point since dawn."
      -> stirs 0.57, tone -0.38: urgency 0.41, protectiveness 0.39, admiration 0.16
  MEMORY: I tried to walk out through the shed door to the quay wall by the bollards, looking toward the harbour entrance at the incoming skiff. Then I tried to
      -> stirs 0.55, tone -0.35: suspicion 0.50, protectiveness 0.37, urgency 0.09
  MEMORY: I concluded this about Wren Halloway: She reads the wind and the harbour entrance as well as he does.
      -> stirs 0.42, tone +0.28: admiration 0.74, protectiveness 0.18
  MEMORY: I concluded that An unfamiliar person standing on the quay with a clear view of the breakwater.
      -> stirs 0.68, tone -0.51: suspicion 0.99
  MEMORY: I heard Wren Halloway say: "Wind'll hold till mid-afternoon. We could make the point and back before she turns." I was standing on the ground beside t
      -> stirs 0.56, tone -0.09: protectiveness 0.51, urgency 0.30, admiration 0.11
  MEMORY: I heard Wren Halloway say "Wind'll hold till mid-afternoon. We could make the point and back before she turns."
      -> stirs 0.54, tone -0.03: protectiveness 0.52, urgency 0.35, admiration 0.08
  MOOD READ (spectrums | moods): playfulness -0.83, boldness +0.64, engagement +0.64, openness -0.57, sociability -0.56 | resolve 0.98, protectiveness 0.96, urgency 0.89, curiosity 0.70, suspicion 0.55
  mood after: protectiveness +0.59, urgency +0.50, resolve +0.46, suspicion +0.41, playfulness -0.37
  HANDED: now ['protectiveness (Her chin drops and her eyes fix on the unfolded card in her ...)', 'dread (Her chin drops and her eyes fix on the unfolded card in her ...)', 'a fear come true (Her chin drops and her eyes fix on the unfolded card in her ...)']
          beneath ['suspicion (I concluded that An unfamiliar person standing on the quay w...)', 'protectiveness (Will Wren and Jonah sail the Tern to the Point today, and wi...)']
          mood ['protectiveness', 'urgency', 'resolve', 'suspicion']
  -- Aldo Halloway THEN:
     Does: Walk the remaining paces toward Wren and Jonah until he is within two strides of them, then stop
     Does: Stand still and watch Wren's face as she reads the card, letting his eyes go to her expression rather than the paper in her hands
  -- AFTER, own acts:
     You Walk the remaining paces toward Wren and Jonah until he is within two strides of them, then stop
        against 0.13, honours 0.55, regard +0.08, wanted else 0.52, eased/stoked +0.30
     You Stand still and watch Wren's face as she reads the card, letting his eyes go to her expression rather than
        against 0.09, honours 0.81, regard +0.35, wanted else 0.57, eased/stoked +0.38
     You held back from: Stay back and let her read it without me leaning over her shoulder
        against 0.25, honours 0.82, regard +0.40, wanted else 0.51, eased/stoked -0.04
     felt: pride 0.07, shame 0.13, frustration 0.52, pride 0.32, shame 0.09, frustration 0.57, pride 0.30, shame 0.25, frustration 0.51
     mood after: protectiveness +0.61, urgency +0.52, resolve +0.48, suspicion +0.42, playfulness -0.39  (stored surface: frustration (You Stand still and watch Wren's face as she reads the card,...))

## Wren Halloway (turn 2) -- BEFORE THE CALL
  carried in: urgency +0.69, resolve +0.68, guilt +0.65, playfulness -0.48, haunted +0.47
  EVENT current:4:15: Jonah Pell says: "Go on, then. The coach won't wait. I'll write. I'll look after the Tern."
      -> stirs 0.95: guilt 0.65, resolve 0.11, moved 0.07
  EVENT current:4:micro:1:6:0: Aldo Halloway closes the last few paces along the breakwater stone and halts within arm's reach of Wren, body angled into the wind, weight settling onto his heels.
      -> stirs 0.83: dread 0.32, guilt 0.26, urgency 0.10
  EVENT current:4:16: Jonah Pell steps back from you along the harbour wall.
      -> stirs 0.72: guilt 0.39, resolve 0.19, urgency 0.14
  EVENT current:4:micro:1:6:1: Aldo's gaze fixes on Wren's face — not the card, not Jonah — and holds there, still and searching.
      -> stirs 0.91: guilt 0.51, dread 0.23, resolve 0.07
  WORRY c0: the card in her hand — unfolding it now
      -> weighs 0.68, stirs 0.94: anticipation 0.22, resolve 0.22, urgency 0.19
  WORRY c1: the unopened acceptance letter in the satchel
      -> weighs 0.84, stirs 0.99: urgency 0.38, guilt 0.19, resolve 0.16
  WORRY c2: Friday's coach and the promise that won't fit on it
      -> weighs 0.94, stirs 0.99: guilt 0.53, urgency 0.27, resolve 0.17
  MEMORY: You are in the harbour wall. A long stone breakwater running east from the quay to the lighthouse point, wide enough for two men to walk abreast. The 
      -> stirs 0.88, tone -0.16: urgency 0.41, guilt 0.27, resolve 0.15
  MEMORY: Jonah Pell came in. I saw Jonah Pell boot hanging over the edge. I heard Jonah Pell say: "Three days," I heard Jonah Pell say: "Your father reckons th
      -> stirs 0.90, tone -0.35: urgency 0.44, guilt 0.29, resolve 0.14
  MEMORY: I tried to slide the unopened letter into the canvas satchel without looking down, pulling the strap closed after. Then I said "Nearly. That skiff's c
      -> stirs 0.88, tone -0.53: urgency 0.62, guilt 0.23, resolve 0.11
  MEMORY: I saw Jonah Pell squint at the channel toward the incoming boat. I heard Jonah Pell say: "Come out in the Tern with me this afternoon," I heard Jonah 
      -> stirs 0.82, tone -0.20: guilt 0.36, nostalgia 0.21, urgency 0.15
  MEMORY: I tried to move her hand from the satchel strap at her hip to the iron rail, fingers closing on salt-pitted metal where names are carved. Then I said 
      -> stirs 0.88, tone -0.40: urgency 0.45, guilt 0.29, resolve 0.11
  MEMORY: I saw Jonah Pell run his thumb along the carving on the iron rail. I heard Jonah Pell say: "Fourteen, we were. You remember what we promised up here?"
      -> stirs 0.98, tone -0.57: guilt 0.70, resolve 0.11
  MEMORY: I heard Aldo Halloway say "The Tern draws three foot. Shelf's at two and falling. You go now, you've got the tide with you to the Point. Coming back's
      -> stirs 0.82, tone -0.52: urgency 0.74, guilt 0.10, resolve 0.09
  MEMORY: I tried to look down at the carved initials in the iron rail where they cut their names at fourteen. Then I said 'Aye. I remember.' Then I tried to re
      -> stirs 0.92, tone -0.46: urgency 0.50, guilt 0.24, resolve 0.11
  MOOD READ (spectrums | moods): playfulness -0.97, engagement +0.70, tension +0.49, boldness +0.49, pleasure -0.48 | resolve 0.98, urgency 0.97, guilt 0.90, haunted 0.90, regret 0.71
  mood after: urgency +0.81, resolve +0.79, guilt +0.78, playfulness -0.60, haunted +0.59
  HANDED: now ['guilt (Jonah Pell says: "Go on, then. The coach won\'t wait. I\'ll wr...)']
          beneath ['guilt (I saw Jonah Pell run his thumb along the carving on the iron...)', 'urgency (I heard Aldo Halloway say "The Tern draws three foot. Shelf\'...)']
          mood ['urgency', 'resolve', 'guilt', 'serious']
  -- Wren Halloway THEN:
     Does: Let the pressing stop — go still on the card, the wind taking the edges where her thumbs held them
     Does: Look up from the card at Jonah, who has stepped back along the wall
     Says (flat, the weight of it — not a question): "You saved for this."
     Does: Turn from Jonah to look at Aldo, standing within arm's reach
     Says (quiet, direct — not quite an accusation): "You knew."
  -- AFTER, own acts:
     You Let the pressing stop — go still on the card, the wind taking the edges where her thumbs held them
        against 0.31, honours 0.54, regard -0.35, wanted else 0.90, eased/stoked +0.51
     You Look up from the card at Jonah, who has stepped back along the wall
        against 0.06, honours 0.56, regard -0.27, wanted else 0.67, eased/stoked +0.59
     You said: "You saved for this."
        against 0.08, honours 0.64, regard -0.30, wanted else 0.72, eased/stoked +0.56
     You Turn from Jonah to look at Aldo, standing within arm's reach
        against 0.04, honours 0.68, regard -0.29, wanted else 0.71, eased/stoked +0.67
     You said: "You knew."
        against 0.04, honours 0.85, regard -0.07, wanted else 0.87, eased/stoked +0.57
     You held back from: Hold it in and say nothing — the guilt is too heavy for words
        against 0.20, honours 0.83, regard +0.22, wanted else 0.86, eased/stoked +0.37
     felt: shame 0.35, frustration 0.90, shame 0.27, frustration 0.67, shame 0.30, frustration 0.72, shame 0.29, frustration 0.71, shame 0.07, frustration 0.87, pride 0.17, shame 0.20, frustration 0.86
     mood after: urgency +0.90, resolve +0.87, guilt +0.78, playfulness -0.67, haunted +0.65  (stored surface: frustration (You Let the pressing stop — go still on the card, the wind t...))

====================================================================================================
TURN 2 >>> "Go on, then," Jonah says, and his voice nearly holds. "The coach won't wait. I'll write. I'll look after the Tern." He steps back to let her pass.
--- narration ---
His boot finds the stone behind him and the gale fills the gap he opened. Two paces, three — enough distance for the wind to come between them clean, pulling at the soaked wool across his shoulders, finding the mended patches at his elbows where the stitching has gone loose.

Wren's chin drops. Her eyes go to the paper in her hands and her body angles to shield it — shoulder into the gust, the old reflex of someone who has spent a life keeping wind off a chart. But her hands go still. The pressing stops, the deliberate flattening she'd been working gone out of her fingers, and the wind finds the edges where her thumbs had held. The stiff card-stock lifts and flutters, one corner curling up and catching the grey light before the next gust folds it back down.

She lifts her gaze from the card to him. He is standing back along the wall where he stepped, the wind pulling at his jumper, and s

## Isolde Varga (turn 1) -- BEFORE THE CALL
  carried in: energy -0.40, tension -0.40
  EVENT current:1:12: Tomas Rell crosses to her and sets the printer's proof on the music rest in front of her.
      -> stirs 0.83: envy 0.23, suspicion 0.19, jealousy 0.11
  EVENT current:1:13: Tomas Rell says under their breath: "It's printed. I. Varga, under the middle theme. I wanted you to see it before anyone else did."
      -> stirs 0.86: suspicion 0.32, envy 0.19, jealousy 0.13
  WORRY c0: Rell has not given her the page — he redirected to asking her to play the melody
      -> weighs 0.91, stirs 0.92: suspicion 0.30, anger 0.27, reproach 0.13
  WORRY c1: The notation is still in his hand, rolled at his side
      -> weighs 0.92, stirs 0.92: anger 0.37, suspicion 0.25, resolve 0.10
  WORRY c2: She has demanded the notation three times and he has not produced it
      -> weighs 0.91, stirs 0.94: anger 0.49, suspicion 0.21, resentment 0.12
  WORRY c3: Lanzi's condition remains — her name on a melody she has not verified
      -> weighs 0.83, stirs 0.95: resolve 0.29, suspicion 0.13, distress 0.09
  MEMORY: You are in Rehearsal Room. A high-ceilinged room with pale walls recently repainted, the plaster still faintly scented with limewash. An upright piano
      -> stirs 0.50, tone -0.18: jealousy 0.34, suspicion 0.21, envy 0.15
  MEMORY: The lanky young man came in. I heard the lanky young man say: "Tomas Rell. I've a letter for Count Lanzi from his cousin in the capital -- they told m
      -> stirs 0.56, tone -0.23: jealousy 0.32, envy 0.32, suspicion 0.18
  MEMORY: I heard Tomas Rell say: "May I?" I saw Tomas Rell play sixteen bars from the beginning, bright and headlong, the ink-stained cuffs of his white shirt 
      -> stirs 0.72, tone -0.35: envy 0.80, jealousy 0.15
  MEMORY: I saw Tomas Rell rise from the piano bench and turns toward Celestine Moreau. I saw Tomas Rell bow deeply from the waist to Celestine Moreau, holding 
      -> stirs 0.82, tone -0.55: envy 0.43, jealousy 0.39, suspicion 0.13
  MEMORY: I tried to straighten from the piano lid, lift fingers from the damp pages, and turn to face Tomas Rell across the room. Then I said "Supper, then. An
      -> stirs 0.63, tone -0.35: jealousy 0.40, resolve 0.23, suspicion 0.14
  MEMORY: I heard Tomas Rell say: "Full orchestra -- pairs of winds, four horns, timpani, and a harp if the house can find one. And in the middle section the st
      -> stirs 0.85, tone -0.55: envy 0.46, jealousy 0.33, suspicion 0.19
  MEMORY: I heard Tomas Rell say "Full orchestra -- pairs of winds, four horns, timpani, and a harp if the house can find one. And in the middle section the str
      -> stirs 0.83, tone -0.51: envy 0.44, jealousy 0.32, suspicion 0.20
  MEMORY: I suspected this about Celestine Moreau: Engaged by Rell writing for her voice specifically; the capital connection makes it more than professional in
      -> stirs 0.73, tone -0.59: jealousy 0.58, envy 0.25, suspicion 0.16
  MOOD READ (spectrums | moods): playfulness -0.80, openness -0.61, engagement +0.48, sociability -0.42, energy -0.42 | resolve 0.92, envy 0.76, curiosity 0.72, anger 0.67, suspicion 0.63
  mood after: energy -0.34, envy +0.34, jealousy +0.29, suspicion +0.27, resolve +0.25
  HANDED: now ['suspicion (Tomas Rell says under their breath: "It\'s printed. I. Varga,...)', "envy (Tomas Rell crosses to her and sets the printer's proof on th...)"]
          beneath ['envy (I heard Tomas Rell say: "May I?" I saw Tomas Rell play sixte...)', 'jealousy (I suspected this about Celestine Moreau: Engaged by Rell wri...)']
          mood ['drained', 'envy', 'jealousy', 'suspicion']
  -- Isolde Varga THEN:
     Does: Look down at the printer's proof on the music rest, reading the printed lines — her name set under the middle theme
     Does: Look up from the proof toward Rell across the room
     Says (flat, controlled — the precision of someone stating a fact that costs her): "Printed. My name, on a melody I have not verified."
     Says (pressing, exact — the demand restated against a different object): "The notation, Mr. Rell. Not the programme."
  -- AFTER, own acts:
     You Look down at the printer's proof on the music rest, reading the printed lines — her name set under the mid
        against 0.10, honours 0.78, regard -0.39, wanted else 0.76, eased/stoked +0.67
     You Look up from the proof toward Rell across the room
        against 0.02, honours 0.72, regard +0.07, wanted else 0.68, eased/stoked +0.58
     You said: "Printed. My name, on a melody I have not verified."
        against 0.02, honours 0.94, regard +0.40, wanted else 0.80, eased/stoked +0.20
     You said: "The notation, Mr. Rell. Not the programme."
        against 0.02, honours 0.94, regard +0.45, wanted else 0.60, eased/stoked +0.10
     You held back from: Accept the recognition — her name, printed, after eleven years; let the verification go
        against 0.11, honours 0.97, regard +0.46, wanted else 0.86, eased/stoked +0.19
     felt: shame 0.39, frustration 0.76, pride 0.07, shame 0.02, frustration 0.68, pride 0.40, shame 0.02, frustration 0.80, pride 0.44, shame 0.02, frustration 0.60, pride 0.41, shame 0.11, frustration 0.86
     mood after: envy +0.36, jealousy +0.31, suspicion +0.29, resolve +0.27  (stored surface: frustration (You held back from: Accept the recognition — her name, print...))

====================================================================================================
TURN 1 >>> Tomas realises she isn't in the practice room at all -- the voice came from beyond the far door. He takes the proof and goes out onto the stage, where Miss Varga sits alone at the stage piano, and sets it on the music rest in front of her, open to the overture. "It's printed. I. Varga, under the middle theme. I wanted you to see it before anyone else did."
--- narration ---
Isolde's gaze drops to the proof on the music rest. Her eyes move across the printed lines — the bold serif of his name above the overture, then the smaller type below the middle section — reading without touching the page, hands flat on the keys, the tortoiseshell pince-nez catching a faint glint of morning light from the proscenium opening above.

She lifts her head and looks at him.

She says something. The stage plaster takes it apart before it crosses the distance between them — <i>...verified... notation... programme...</i> — three words he can hold, the rest stripped by the cavernous air and gone.

Close by, the unfamiliar man straightens in his chair and turns to face him. His free hand comes up in a curt, dismissing wave — small, definite, the gesture of someone who has already decided this conversation is over. What he says follows it, arriving in the same broken pieces: <i>...

## Isolde Varga (turn 2) -- BEFORE THE CALL
  carried in: envy +0.36, jealousy +0.31, suspicion +0.29, resolve +0.27
  EVENT current:1:12: Tomas Rell sits down on the far end of the piano bench, leaving room.
      -> stirs 0.54: suspicion 0.32, envy 0.14, resolve 0.13 (nothing much 0.13)
  EVENT current:1:13: Tomas Rell says under their breath: "Will you play it for me? The way you first wrote it. I've only ever heard it the way Lanzi had it."
      -> stirs 0.97: fears_confirmed 0.18, suspicion 0.18, resolve 0.17
  WORRY c0: The proof is printed with her name but the notation is still not in her hands
      -> weighs 0.88, stirs 0.97: suspicion 0.40, resolve 0.18, envy 0.08
  WORRY c1: The rolled manuscript is held by an unfamiliar person close by — it may be the score she needs
      -> weighs 0.76, stirs 0.94: suspicion 0.58, urgency 0.14, envy 0.10
  WORRY c2: She has not yet verified whether the middle theme is hers
      -> weighs 0.83, stirs 0.97: suspicion 0.54, resolve 0.27
  WORRY c3: Lanzi's condition remains — her name on a melody she has not confirmed
      -> weighs 0.90, stirs 0.98: suspicion 0.38, resolve 0.30, envy 0.11
  MEMORY: You are in Rehearsal Room. A high-ceilinged room with pale walls recently repainted, the plaster still faintly scented with limewash. An upright piano
      -> stirs 0.63, tone -0.26: resolve 0.31, suspicion 0.27, jealousy 0.15
  MEMORY: The lanky young man came in. I heard the lanky young man say: "Tomas Rell. I've a letter for Count Lanzi from his cousin in the capital -- they told m
      -> stirs 0.69, tone -0.35: envy 0.33, suspicion 0.33, jealousy 0.14
  MEMORY: I heard Tomas Rell say: "May I?" I saw Tomas Rell play sixteen bars from the beginning, bright and headlong, the ink-stained cuffs of his white shirt 
      -> stirs 0.82, tone -0.49: envy 0.83, jealousy 0.06, suspicion 0.06
  MEMORY: I saw Tomas Rell rise from the piano bench and turns toward Celestine Moreau. I saw Tomas Rell bow deeply from the waist to Celestine Moreau, holding 
      -> stirs 0.84, tone -0.52: jealousy 0.48, envy 0.25, protectiveness 0.18
  MEMORY: I tried to straighten from the piano lid, lift fingers from the damp pages, and turn to face Tomas Rell across the room. Then I said "Supper, then. An
      -> stirs 0.73, tone -0.47: resolve 0.51, jealousy 0.19, protectiveness 0.09
  MEMORY: I heard Tomas Rell say: "Full orchestra -- pairs of winds, four horns, timpani, and a harp if the house can find one. And in the middle section the st
      -> stirs 0.88, tone -0.54: jealousy 0.39, envy 0.28, protectiveness 0.19
  MEMORY: I saw Tomas Rell lean toward Celestine Moreau, his elbows resting on the table cloth. I heard Tomas Rell say: "The director of the Grand Theatre in th
      -> stirs 0.90, tone -0.59: jealousy 0.37, envy 0.33, protectiveness 0.20
  MEMORY: I tried to stop mid-stride and turn to face Tomas Rell across the room. Then I said 'The house does not write, Mr. Rell. I do.' Then I tried to turn a
      -> stirs 0.85, tone -0.49: resolve 0.67, jealousy 0.12, suspicion 0.07
  MOOD READ (spectrums | moods): playfulness -0.80, openness -0.59, sociability -0.49, engagement +0.48, pleasure -0.45 | resolve 0.96, envy 0.77, curiosity 0.68, anger 0.66, suspicion 0.64
  mood after: envy +0.55, resolve +0.53, jealousy +0.46, suspicion +0.45, openness -0.36
  HANDED: now ['a fear come true (Tomas Rell says under their breath: "Will you play it for me...)', 'suspicion (Tomas Rell says under their breath: "Will you play it for me...)', 'resolve (Tomas Rell says under their breath: "Will you play it for me...)']
          beneath ['envy (I heard Tomas Rell say: "May I?" I saw Tomas Rell play sixte...)', 'resolve (I tried to stop mid-stride and turn to face Tomas Rell acros...)']
          mood ['envy', 'resolve', 'jealousy', 'suspicion']
  -- Isolde Varga THEN:
     Does: Lift fingers from the piano keys without pressing them — the withholding of the note Rell asked for
     Does: Turn her head to look at Rell seated beside her on the bench
     Says (low, precise, the question held like a blade turned sideways): "What do you mean — the way Lanzi had it."
  -- AFTER, own acts:
     You Lift fingers from the piano keys without pressing them — the withholding of the note Rell asked for
        against 0.24, honours 0.86, regard +0.21, wanted else 0.94, eased/stoked +0.40
     You Turn her head to look at Rell seated beside her on the bench
        against 0.14, honours 0.47, regard +0.00, wanted else 0.74, eased/stoked +0.56
     You said: "What do you mean — the way Lanzi had it."
        against 0.06, honours 0.82, regard +0.17, wanted else 0.84, eased/stoked +0.45
     You held back from: Play the melody as she first wrote it — the keys are under her hands, Rell is beside her, 
        against 0.35, honours 0.87, regard -0.12, wanted else 0.90, eased/stoked +0.59
     felt: pride 0.16, shame 0.24, frustration 0.94, shame 0.14, frustration 0.74, pride 0.17, shame 0.06, frustration 0.84, shame 0.35, frustration 0.90
     mood after: envy +0.60, resolve +0.58, jealousy +0.50, suspicion +0.49, openness -0.41  (stored surface: frustration (You Lift fingers from the piano keys without pressing them —...))

====================================================================================================
TURN 2 >>> Tomas sits down on the far end of the piano bench, careful to leave room. "Will you play it for me? The way you first wrote it. I've only ever heard it the way Lanzi had it."
--- narration ---
Varga's fingers rise from the keys and hang there — suspended above the ivory, not pressing, not lifting away. She turns her head and looks at him along the bench. Her jaw tightens, a small contraction at the hinge, and the question comes low and precise, each word held flat and sideways like something she has decided not to let cut.

"What do you mean — the way Lanzi had it."

The unfamiliar man shifts his weight on the bench, the wood giving a faint creak under the redistribution, and his gaze settles on Tomas without hurry.

"She's asking what I did to it. Tell her — or play it, and let her hear for herself."

Under the hem of his coat, a dark patch widens against the polished wood — the rainwater the wool has carried since the harbour wall, wicking slow from fabric into grain. Isolde's fingers stay lifted above the keys, sounding nothing. The two vertical lines between her brows deep
```
