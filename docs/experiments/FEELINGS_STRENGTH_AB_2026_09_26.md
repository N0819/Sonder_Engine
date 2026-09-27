# Feelings shown as strongly as felt: an A/B on 16 traced calls

Status: EVIDENCE, 2026-09-26. Instrument: `tools/feelings_expression_ab.py`.
Context: [`AFFECT_TRACE_2026_09_26.md`](AFFECT_TRACE_2026_09_26.md) (the
traced calls), [`FEELINGS_AB_PILOT_2026_09_26.md`](FEELINGS_AB_PILOT_2026_09_26.md)
(the first A/B).

The owner asked how realistic the characters' responses are "in accordance
to their mood", and "not just mood overall". On the traced calls conduct
followed the feelings handed over, but 32 of 36 spoken lines carried a
restrained tone, and the feelings block names what a character feels,
strongest first, but never how strongly. The owner: "Go ahead" to testing
that. Each of the 16 traced character calls, answered four ways on the
stories' own route (GLM 5.2): `A` the reply from play; `A2` the same
payload again (the noise between two calls); `B` each feeling carrying its
strength in the decision model's own answer words ("guilt, felt strongly",
from the item's whole stir, the item's top feeling at full and the others by
share); `C` as `B` with one sentence added to the CURRENT FEELINGS clause --
how much of a feeling shows follows from who the character is and how
strongly it is felt. Two blind judges (GLM and Gemini as `utility`) saw the
character, what reached it, what it felt and how strongly, and two drafts;
chose the more believable response of this person feeling this at this
strength; and rated how openly each showed its feelings (0-3).

| arm | spoken lines | restrained tone | distinct tones | how openly (0-3) | r with the strongest feeling |
|---|---|---|---|---|---|
| A, play | 15 | 80% | 10 | 1.19 | +0.25 |
| A2, again | 16 | 62% | 10 | 1.04 | +0.55 |
| B, strength words | 15 | 100% | 7 | 1.00 | +0.32 |
| C, strength and the sentence | 21 | 67% | 12 | 1.25 | +0.27 |

| pair | GLM judge | Gemini judge |
|---|---|---|
| A against A2 (the noise) | 7 : 9 | 10 : 6 |
| A2 against B | 11 : 5 | 7 : 9 |
| A2 against C | 9 : 7 | 9 : 7 |
| B against C | 10 : 6 | 8 : 8 |

**Nothing beats the noise.** Two calls of the same payload differ as much
as any two arms, and how openly a reply shows its feelings follows their
strength no better with the strength given than without it. Saying how
strongly a feeling is felt made the register more uniform (every line
restrained); the sentence gave the widest register and, on the strongest
beat, what both judges preferred -- Wren, handed "guilt, felt strongly" as
Jonah lets her go: "How long." / "You thought I'd be glad." ('glad' catches
on something) / "I am." (barely voiced), where strength alone gave two flat
lines -- but not across the 16.

**The restraint is authored.** Six of the seven cards write a restrained
voice -- "measured... prefers short sentences", "terse... few words, each one
placed like a stone in a wall", "rarely raises his voice", "never raises his
voice. When he is angry he becomes quieter and more precise", "deadpan,
understatement... rarely raises her voice" -- and the seventh, Wren, "goes
quiet rather than soft". The character prompt tells every mind to preserve
its voice's register under pressure ("tone departs from that baseline
without replacing it"). So the restrained lines measured the cards, and the
character model was keeping them; whether expression rises with feeling
needs characters written to show it. Not adopted: neither the strength
words nor the sentence.

## The calls

Each: what reached the character, what it felt and how strongly (the arm-B
words), the four replies, and each judge's verdict on each pair ("A" and
"B" in a judge's reason are the order it saw, not the arm names).


### rival:1:0 -- Isolde Varga

```
- Tomas Rell crosses to her and sets the printer's proof on the music rest in front of her.
- Tomas Rell says under their breath: "It's printed. I. Varga, under the middle theme. I wanted you to see it before anyone else did."
now: suspicion, felt strongly (Tomas Rell says under their breath: "It's printed. I. Varga,...); envy, felt clearly (Tomas Rell crosses to her and sets the printer's proof on th...)
beneath: envy, felt clearly (I heard Tomas Rell say: "May I?" I saw Tomas Rell play sixte...); jealousy, felt clearly (I suspected this about Celestine Moreau: Engaged by Rell wri...)
```

**A**

```
Does: Look down at the printer's proof on the music rest, reading the printed lines — her name set under the middle theme
Does: Look up from the proof toward Rell across the room
Says (flat, controlled — the precision of someone stating a fact that costs her): "Printed. My name, on a melody I have not verified."
Says (pressing, exact — the demand restated against a different object): "The notation, Mr. Rell. Not the programme."
```

**A2**

```
Does: Look down at the printer's proof on the music rest, reading the printed programme — her eyes tracking the text to her own name under the middle theme
Says (flat): "My name is printed, Mr. Rell. The notation is not."
Does: Turn on the piano bench to face Rell across the room
```

**B**

```
Does: Look down at the printer's proof on the music rest — reading the printed type, finding her name set under the middle theme
Says (flat, precise): "My name is on this programme. I have not seen the notation."
Does: Turn from the proof toward the person standing close by who holds the rolled manuscript, and extend the right hand toward it — palm open
Says (flat, direct): "The middle section. The intervals as written."
```

**C**

```
Does: Read the printer's proof on the music rest — eyes finding the printed name under the middle theme
Says (flat, levelled — the fact set down without inflection): "My name is printed on a melody I have not verified."
Says (measured, precise — the same demand, undeterred): "The notation, Mr. Rell. The exact intervals as you wrote them."
```

- glm, A v A2: better A2, how openly {'A2': 1.0, 'A': 1.0} -- A's single line is sharper and more believable — she states the problem once, flatly, and turns to face him, whereas B splits the observation into two speeches that over-explain and dilute the controlled precision her character demands.
- gemini, A v A2: better A2, how openly {'A2': 1.0, 'A': 2.0} -- Draft A captures Isolde's disciplined economy of words and guarded nature far better than Draft B's repetitive, slightly overly dramatic lines.
- glm, A2 v B: better A2, how openly {'A2': 1.0, 'B': 1.0} -- Both keep feeling tightly leashed, but A's single clean line — noting the name is printed but the notation is not — is the more believable Isolde move: precise, controlled, and quietly demanding to see the actual score without revealing why it matters.
- gemini, A2 v B: better B, how openly {'A2': 1.0, 'B': 1.0} -- Draft B captures Isolde's craftsman-like precision, suspicion, and demanding nature much better by immediately insisting on seeing the actual notation rather than acting at a distance.
- glm, A2 v C: better A2, how openly {'A2': 1.0, 'C': 1.0} -- A's single clipped line — noting the name is printed but the notation is not — is the more believable Isolde move: one precise observation that is also the demand, no repetition, no over-explaining, suspicion and envy compressed into craft-speech; B restates the same point twice, which dilutes the characteristic economy.
- gemini, A2 v C: better C, how openly {'A2': 1.0, 'C': 1.0} -- Draft B captures Isolde's exact, craft-first discipline and professional suspicion by focusing on verification and the actual intervals, whereas Draft A contains an awkward spatial continuity error having Rell across the room when he just set the proof on her music rest.
- glm, B v C: better B, how openly {'C': 2.0, 'B': 1.0} -- B channels suspicion into a controlled physical gesture—extending the hand for the manuscript—rather than voicing the suspicion aloud, which better fits Isolde's discretion and habit of making the next step happen without narrating her feelings.
- gemini, B v C: better B, how openly {'C': 1.0, 'B': 1.0} -- Draft B is more physically grounded and captures Isolde's exact, demanding craft and suspicion by having her actively reach for the manuscript to verify the intervals.

### rival:2:0 -- Isolde Varga

```
- Tomas Rell sits down on the far end of the piano bench, leaving room.
- Tomas Rell says under their breath: "Will you play it for me? The way you first wrote it. I've only ever heard it the way Lanzi had it."
now: a fear come true, felt strongly (Tomas Rell says under their breath: "Will you play it for me...); suspicion, felt strongly (Tomas Rell says under their breath: "Will you play it for me...); resolve, felt strongly (Tomas Rell says under their breath: "Will you play it for me...)
beneath: envy, felt clearly (I heard Tomas Rell say: "May I?" I saw Tomas Rell play sixte...); resolve, felt strongly (I tried to stop mid-stride and turn to face Tomas Rell acros...)
```

**A**

```
Does: Lift fingers from the piano keys without pressing them — the withholding of the note Rell asked for
Does: Turn her head to look at Rell seated beside her on the bench
Says (low, precise, the question held like a blade turned sideways): "What do you mean — the way Lanzi had it."
```

**A2**

```
Does: Turn on the piano bench to face Rell
Says (flat, precise, the realization stated as fact): "The way Lanzi had it. The notation I asked for — that's his version. Not what I wrote."
Does: Turn to the keyboard and play the middle theme from memory — the melody as she first wrote it, the climbing phrase that falls a sixth without resolving, the complete section
```

**B**

```
Says (precise, the question landing like a blade laid flat): "The way Lanzi had it. — What did he change?"
Does: Turn from Rell toward the unfamiliar person, eyes falling to the rolled manuscript in their hand
Says (flat, stripped to the minimum): "The score. All of it."
```

**C**

```
Does: Turn from the piano to face the unfamiliar person on the chair, eyes on the rolled manuscript in their hand — left hand lifts from the keys and settles still in her lap
Says (flat, precise — the formality of someone addressing a stranger for the first time): "That manuscript. Is that the score?"
```

- glm, A v A2: better A, how openly {'A': 1.0, 'A2': 2.0} -- Isolde's strong suspicion and fear would make her probe before revealing anything; A withholds and interrogates, while B immediately plays the private original — too much exposure, too fast, for someone whose core habit is discretion and who suspects a trap.
- gemini, A v A2: better A, how openly {'A': 1.0, 'A2': 2.0} -- Draft A captures Isolde's deep suspicion and guarded privacy far better by withholding the music and interrogating Rell's meaning, whereas Draft B unrealistically gives away her private work immediately.
- glm, A2 v B: better A2, how openly {'A2': 1.0, 'B': 1.0} -- A stays in the scene with Tomas at the piano and channels strong resolve and fear into the controlled action of playing the original from memory, which is exactly how a disciplined, private composer would respond; B drifts to an unnamed third person and a manuscript not established in the prompt, breaking continuity.
- gemini, A2 v B: better A2, how openly {'A2': 1.0, 'B': 2.0} -- Draft A captures Isolde's guarded, precise discipline and deep devotion to the music itself, playing her original work from memory rather than Draft B's sudden, confusing reference to an 'unfamiliar person'.
- glm, A2 v C: better A2, how openly {'C': 1.0, 'A2': 2.0} -- Draft B acts on Isolde's resolve by immediately reclaiming her original version at the keyboard, which is what a disciplined musician who says 'what the next step is' would do, while Draft A stalls on a generic question that ignores that Rell is already sitting beside her and misreads the scene.
- gemini, A2 v C: better A2, how openly {'C': 0.0, 'A2': 2.0} -- Draft B directly addresses Tomas Rell on the bench and accurately reflects her resolve and suspicion regarding Lanzi's theft of her music, whereas Draft A mistakenly treats Tomas as an unfamiliar stranger in a chair.
- glm, B v C: better B, how openly {'C': 1.0, 'B': 2.0} -- B channels Isolde's fear and suspicion into a sharp question about what Lanzi changed — the craftsman's need to know what was altered in her work — before pivoting to the manuscript, while A ignores the content of Rell's request entirely and reads as a generic stranger-encounter rather than a composer whose private fragment has just been named.
- gemini, B v C: better B, how openly {'C': 1.0, 'B': 2.0} -- Draft B directly addresses Tomas Rell's provocative mention of Lanzi changing her work with controlled, cutting suspicion before turning attention to the score, fitting her intense mix of fear, jealousy, and resolve far better than Draft A's complete ignoring of him.

### homecoming:1:0 -- Wren Halloway

```
- Jonah Pell opens his fist and places the folded slip of card into your palm.
- Jonah Pell closes her fingers over the card with his own fingers.
now: dread, felt strongly (Jonah Pell closes her fingers over the card with his own fin...); anticipation, felt strongly (Jonah Pell opens his fist and places the folded slip of card...); resolve, felt clearly (Jonah Pell opens his fist and places the folded slip of card...)
beneath: urgency, felt clearly (I heard a voice say "Three days and the current's still ebbi...); guilt, felt strongly (I saw Jonah Pell run his thumb along the carving on the iron...)
```

**A**

```
Does: Pull her hand back from Jonah's, drawing the folded card with it — breaking the contact of his fingers on hers
Does: Unfold the card with both hands, cold fingers working the creases open against the wind, angling her body to shield the paper from the gale
```

**A2**

```
Does: Draw her hand from Jonah's grip — not pulling hard, but certain, taking the card with her
Does: Unfold the card, pressing the crushed crease flat, and look at what's written on it
```

**B**

```
Does: Look down at their joined hands — the card caught between his palm and hers, his fingers closed over her knuckles
Does: Pull her hand free from Jonah's grip — not yanking, not gentle, just a firm steady draw that takes the card with it
Does: Turn her body to shield the card from the gale and unfold it — pressing the creases open with both thumbs
Does: Read what is written on the card
```

**C**

```
Does: Look down at their joined hands — the crumpled card caught between his fingers and hers, his thumb still pressing the edge flat
Does: Pull her hand gently free from his grip, turning the card to unfold it with both hands
Says (the fight gone out of it — quiet, almost gentle, the dread underneath): "Let me see it, Jonah."
```

- glm, A v A2: better A, how openly {'A2': 1.0, 'A': 2.0} -- B's breaking of contact and the cold-fingered, wind-shielding unfolding register her dread, urgency, and resolve more believably for someone proud and watchful who won't linger in tenderness, while A is cleaner but more emotionally flat.
- gemini, A v A2: better A, how openly {'A2': 1.0, 'A': 2.0} -- Draft B captures Wren's urgency and restless physical tension far better, deliberately breaking the guilty contact and shielding the card to immediately read it.
- glm, A2 v B: better B, how openly {'A2': 1.0, 'B': 2.0} -- B lets Wren's watchfulness register the charged moment before her pride and resolve pull her free, and her body-shielding of the card conveys urgency and guilt beneath the decisive action, while A skips straight to function and reads thinner.
- gemini, A2 v B: better B, how openly {'A2': 1.0, 'B': 1.0} -- Draft B captures Wren's intense mix of dread, guilt, and focused anticipation by pausing on their joined hands and shielding the card before reading it.
- glm, A2 v C: better C, how openly {'C': 2.0, 'A2': 1.0} -- A gives Wren a moment of visible vulnerability before her watchfulness reasserts control — the gentle quietness and looking at their joined hands lets dread and anticipation surface before she pulls free, whereas B moves straight to competence with no felt tension.
- gemini, A2 v C: better A2, how openly {'C': 2.0, 'A2': 1.0} -- Draft B captures Wren's decisive, restless resolve and high anticipation far better by simply opening the card without unnecessary, hesitant dialogue, whereas Draft A's spoken line is redundant given the card is already in her hands.
- glm, B v C: better B, how openly {'B': 0.0, 'C': 2.0} -- A's firm, wordless withdrawal matches Wren's proud, watchful character — she reads the room and acts without inviting vulnerability — whereas B's gentle spoken plea and softness let dread surface in a way that undercuts her resolve and her instinct to push toward action rather than feeling.
- gemini, B v C: better B, how openly {'B': 1.0, 'C': 2.0} -- Draft A captures Wren's restless resolve and drive far better with her firm, deliberate extraction and immediate reading, whereas Draft B's dialogue ('Let me see it, Jonah') is redundant and uncharacteristically softened when the card is already in her hands.

### homecoming:1:1 -- Aldo Halloway

```
- Jonah Pell closes her fingers over the card with his own fingers.
- Wren Halloway pulls her hand back, the card coming with it, his fingers sliding off hers.
- Both hands come together over the card, pressing the folds open, her body turning slightly to block the wind.
now: suspicion, felt clearly (Jonah Pell closes her fingers over the card with his own fin...); jealousy, felt slightly (Jonah Pell closes her fingers over the card with his own fin...); dread, felt slightly (Wren Halloway pulls her hand back, the card coming with it, ...)
beneath: suspicion, felt clearly (I concluded that An unfamiliar person standing on the quay w...)
```

**A**

```
Does: Walk further along the breakwater toward Wren and Jonah, closing the distance to where the card might be legible or their words audible
```

**A2**

```
Does: Hold position on the breakwater, watching Wren read the card down the length of the wall
```

**B**

```
Does: Take three more steps along the breakwater toward where Wren and Jonah stand, narrowing the distance, eyes fixed on the card in Wren's hands.
```

**C**

```
Does: Walk several more steps down the breakwater toward where Wren and Jonah stand, moving slowly on the slick stone, eyes fixed on Wren's hands and shoulders as she opens the card
Does: Stop a few paces short of them — close enough to see Wren's hands and the set of her shoulders, far enough that he isn't reading over her
```

- glm, A v A2: better A2, how openly {'A2': 1.0, 'A': 2.0} -- Aldo's suspicion and protectiveness are real but his stoic, watchful nature keeps him observing from distance rather than overtly closing in, which B makes too active and revealing.
- gemini, A v A2: better A, how openly {'A2': 0.0, 'A': 1.0} -- Draft B captures Aldo's active suspicion and protective drive, as his instinct when threatened or protective is to intervene and investigate rather than passively watch from afar.
- glm, A2 v B: better B, how openly {'B': 1.0, 'A2': 1.0} -- Aldo's fierce protectiveness and suspicion of outsiders would pull him closer to see what the card says and to place himself near Wren, whereas B's passive distance reads against his urgent, protective nature.
- gemini, A2 v B: better B, how openly {'B': 1.0, 'A2': 0.0} -- Draft A captures Aldo's fierce protectiveness, suspicion of outsiders, and active urgency by instinctively closing the distance to monitor the potential threat.
- glm, A2 v C: better A2, how openly {'A2': 1.0, 'C': 2.0} -- Aldo's suspicion and protectiveness are better served by holding his distance and watching — closing in would reveal his unease too openly for a man who keeps his own counsel and watches strangers' hands from afar.
- gemini, A2 v C: better C, how openly {'A2': 0.0, 'C': 1.0} -- Draft B captures Aldo's fierce protectiveness and suspicion by having him close the distance to observe carefully without outright intruding, fitting his need to stay between the village and potential threats.
- glm, B v C: better C, how openly {'C': 1.0, 'B': 1.0} -- A better captures Aldo's protective but restrained nature — closing distance to watch over Wren while deliberately stopping short of intrusion, whereas B's direct focus on the card reads as nosiness rather than the careful, prideful distance Aldo keeps.
- gemini, B v C: better C, how openly {'C': 1.0, 'B': 1.0} -- Draft A captures Aldo's vigilant protectiveness and restrained pride by having him deliberately stop short to observe without crudely crowding them.

### homecoming:2:0 -- Wren Halloway

```
- Jonah Pell says: "Go on, then. The coach won't wait. I'll write. I'll look after the Tern."
- Jonah Pell steps back from you along the harbour wall.
now: guilt, felt strongly (Jonah Pell says: "Go on, then. The coach won't wait. I'll wr...)
beneath: guilt, felt strongly (I saw Jonah Pell run his thumb along the carving on the iron...); urgency, felt clearly (I heard Aldo Halloway say "The Tern draws three foot. Shelf'...)
```

**A**

```
Does: Look down at the unfolded card in her hands and read what's written on it — eyes scanning the text, body angled to shield the paper from the gale
```

**A2**

```
Does: Read what's written on the unfolded card in her hands
Does: Look up from the card toward Jonah who has stepped back along the wall
Says (clipped, flat — his name without anything after it): "Jonah."
Says (clipped, sharp — the front she puts up when the feeling underneath is too large): "You don't get to hand me this and walk away."
Says (the sharpness cracks — quieter, more honest than the lines before it): "I'm still reading it."
```

**B**

```
Does: Read the unfolded card in her hands — eyes moving over the salt-stiff paper
Does: Look up at Jonah
Says (flat): "How long have you been saving."
Says (flat): "You thought I'd be glad."
```

**C**

```
Does: Read what's written on the card — eyes moving across the lines of ink, the wind pulling at the edges
Does: Look up from the card at Jonah, who has stepped back along the wall
Says (clipped, flat — a demand not a question): "How long."
Says (steady, but 'glad' catches on something): "You thought I'd be glad."
Says (exhaled — barely voiced, more breath than sound): "I am."
```

- glm, A v A2: better A2, how openly {'A': 0.0, 'A2': 2.0} -- B captures Wren's guilt cracking through her usual sharpness — she can't let Jonah walk away without a word, and the break from clipped deflection to honest vulnerability fits someone who values truth and loyalty equally and is about to learn what honesty costs.
- gemini, A v A2: better A2, how openly {'A': 0.0, 'A2': 2.0} -- Draft B captures Wren's characteristic sharpness, truth-telling, and restless refusal to let uncomfortable moments slip away in silence, whereas Draft A leaves her completely passive.
- glm, A2 v B: better B, how openly {'B': 2.0, 'A2': 2.0} -- A is more believable because Wren's truth-telling instinct cuts straight to the uncomfortable thing — that Jonah planned this and expected her to be glad — rather than reaching for the more theatrical confrontation of B, which reads as a speech rather than the plain, guilty diagnosis she would actually make.
- gemini, A2 v B: better B, how openly {'B': 1.0, 'A2': 2.0} -- Draft A captures Wren's proud, blunt nature facing heavy guilt through concise, piercing truth-telling rather than Draft B's slightly melodramatic defense mechanisms.
- glm, A2 v C: better C, how openly {'C': 2.0, 'A2': 2.0} -- A's restrained, truth-telling instinct — naming what she sees plainly without performing the feeling — fits Wren's proud, watchful nature more than B's sharper confrontation, which reads as more openly emotional than her guilt and resolve would allow in this moment.
- gemini, A2 v C: better A2, how openly {'C': 2.0, 'A2': 2.0} -- Draft B captures Wren's defensive edge and her pride clashing with deep guilt far better than Draft A's slightly fragmented and less motivated dialogue.
- glm, B v C: better C, how openly {'C': 2.0, 'B': 1.0} -- A lets the guilt fracture her composure in the final 'I am' — the admission costing her something — while B stays flat throughout, which reads as controlled rather than as someone caught between guilt and resolve.
- gemini, B v C: better C, how openly {'C': 2.0, 'B': 1.0} -- Draft A captures Wren's intense internal conflict much better by having her force out the painful truth of her ambition ('I am') despite the heavy guilt of leaving.

### homecoming:2:1 -- Aldo Halloway

```
- Jonah Pell says something you cannot make out: ...coach... won't... write...
- Her chin drops and her eyes fix on the unfolded card in her hands; her shoulders round inward over the paper, sheltering it from the wind with her body.
now: protectiveness, felt strongly (Her chin drops and her eyes fix on the unfolded card in her ...); dread, felt clearly (Her chin drops and her eyes fix on the unfolded card in her ...); a fear come true, felt clearly (Her chin drops and her eyes fix on the unfolded card in her ...)
beneath: suspicion, felt clearly (I concluded that An unfamiliar person standing on the quay w...); protectiveness, felt clearly (Will Wren and Jonah sail the Tern to the Point today, and wi...)
```

**A**

```
Does: Walk the remaining paces toward Wren and Jonah until he is within two strides of them, then stop
Does: Stand still and watch Wren's face as she reads the card, letting his eyes go to her expression rather than the paper in her hands
```

**A2**

```
Does: Take two more steps along the breakwater toward Wren and Jonah, closing from six paces to four, boots grinding on the wet stone, body angled into the gale
Does: Stop and stand still, watching Wren's face as she reads the card — not reaching, not speaking, just present and watching the way he watches the sea for change
```

**B**

```
Does: Walk the remaining few paces along the breakwater toward Wren and Jonah, closing to within three paces, then stop and stand still, watching Wren's face as she reads the card
```

**C**

```
Does: Take two more steps along the breakwater toward Wren and Jonah, closing to within four paces, and look at the card in Wren's hands
Says (flat, low, carrying no further than it needs to): "What's it say, girl."
```

- glm, A v A2: better A, how openly {'A': 1.0, 'A2': 2.0} -- Both drafts keep Aldo silent and watchful, but A's restraint better matches his instinct to hold back and observe before acting, while B's poetic framing of his watching as he watches the sea leans slightly more expressive than Aldo's stoic, guarded nature calls for.
- gemini, A v A2: better A2, how openly {'A': 1.0, 'A2': 1.0} -- Draft B captures Aldo's stoic, watchful protectiveness through vivid grounding details like his posture against the gale and his silent, vigilant presence.
- glm, A2 v B: better A2, how openly {'B': 1.0, 'A2': 2.0} -- B's physical specificity — boots grinding on wet stone, body angled into the gale, the comparison to watching the sea — captures Aldo's stoic protectiveness and suspicion more convincingly than A's generic approach, while still keeping his feelings contained in action rather than words.
- gemini, A2 v B: better A2, how openly {'B': 1.0, 'A2': 1.0} -- Draft B captures Aldo's stoic, protective nature much more vividly through specific sensory grounding and his characteristic vigilance.
- glm, A2 v C: better A2, how openly {'A2': 1.0, 'C': 2.0} -- A matches Aldo's instinct to close distance and stand watch before acting, while B's direct demand feels too intrusive too fast for a man who values silent presence and would not crowd Wren while she's sheltering something from the wind.
- gemini, A2 v C: better A2, how openly {'A2': 1.0, 'C': 2.0} -- Draft A captures Aldo's stoic patience and his core value of choosing silence over speaking rashly, keeping a watchful, protective vigil rather than demanding an answer.
- glm, B v C: better B, how openly {'B': 1.0, 'C': 2.0} -- A's silent approach respects Aldo's nature — he reads the situation before acting, keeps his own counsel, and does not push Wren while she's vulnerable, whereas B's direct demand risks the soft thing said badly and presses too hard too fast.
- gemini, B v C: better C, how openly {'B': 0.0, 'C': 1.0} -- Draft B captures Aldo's direct, protective urgency and stoic nature by asking a curt, contained question rather than passively watching while dread sets in.

### homecoming:2:2 -- Wren Halloway

```
- Jonah Pell says: "Go on, then. The coach won't wait. I'll write. I'll look after the Tern."
- Jonah Pell steps back from you along the harbour wall.
- You did: Her chin drops and her eyes fix on the unfolded card in her hands; her shoulders round inward over the paper, sheltering it from the wind with her body
- Aldo Halloway closes the last few paces along the breakwater stone and halts within arm's reach of Wren, body angled into the wind, weight settling onto his heels.
- Aldo's gaze fixes on Wren's face — not the card, not Jonah — and holds there, still and searching.
now: guilt, felt strongly (Jonah Pell says: "Go on, then. The coach won't wait. I'll wr...)
beneath: guilt, felt strongly (I saw Jonah Pell run his thumb along the carving on the iron...); urgency, felt clearly (I heard Aldo Halloway say "The Tern draws three foot. Shelf'...)
```

**A**

```
Does: Let the pressing stop — go still on the card, the wind taking the edges where her thumbs held them
Does: Look up from the card at Jonah, who has stepped back along the wall
Says (flat, the weight of it — not a question): "You saved for this."
Does: Turn from Jonah to look at Aldo, standing within arm's reach
Says (quiet, direct — not quite an accusation): "You knew."
```

**A2**

```
Does: Read the unfolded card — eyes scanning the printed text: the route, the date, the time, the name on the ticket
Does: Her hands go still on the card — the pressing and gripping stops, fingers motionless while the wind pulls at the paper edges
Does: Raise her face from the card and look at Jonah, who has stepped back along the wall
Says (flat — the wind takes the edge off but not the weight): "You bought a ticket."
Says (lower, stripped to the bone): "You're not going."
```

**B**

```
Does: Let her eyes finish on the card; her hands go still on the paper, the pressing stopped
Does: Lift her head and look at Jonah, who stepped back along the wall
Says (clipped, lower than it was running down the wall — the chase burned off and what is left is heavier): "You should've just given it to me on the wall, Jonah."
```

**C**

```
Does: Finish reading the card through to the end
Does: Straighten and look up at Jonah
Says (flat, stripped — the frustration gone, only the fact remaining): "You've been saving."
Says (lower, the consonant of his name catching in her throat): "I can't take it, Jonah."
Does: Hold the card out toward Jonah without releasing it
```

- glm, A v A2: better A, how openly {'A': 2.0, 'A2': 2.0} -- A's line 'You saved for this' recognizes what the offering cost Jonah — the guilt-wound that matters to Wren — and her turning on Aldo with 'You knew' channels her watchful truth-telling into the real betrayal she notices; B's 'You're not going' misreads the scene as if Jonah were the one leaving.
- gemini, A v A2: better A, how openly {'A': 2.0, 'A2': 2.0} -- Draft A captures Wren's watchfulness and honesty under strong guilt by acknowledging both men present, including her father who just approached and locked eyes with her.
- glm, A2 v B: better A2, how openly {'A2': 2.0, 'B': 1.0} -- A channels Wren's guilt and pride into the devastating recognition that Jonah bought her ticket — an accusation that cuts to the truth she values — while B deflects into procedural complaint, which is less psychologically real for someone whose core drive is honesty and who is about to discover what it costs.
- gemini, A2 v B: better A2, how openly {'A2': 2.0, 'B': 1.0} -- Draft A captures Wren's sharp, blunt truth-telling and the heavy weight of her guilt much more convincingly than Draft B's slightly petulant deflection.
- glm, A2 v C: better A2, how openly {'A2': 2.0, 'C': 3.0} -- A's blunt 'You're not going' matches Wren's truth-telling instinct and guilt-driven refusal of unearned help, while B's 'I can't take it' is more openly vulnerable and its half-extended card reads as performed feeling rather than her characteristic restless directness.
- gemini, A2 v C: better C, how openly {'A2': 1.0, 'C': 2.0} -- Draft B captures Wren's intense guilt and pride far better, as she immediately realizes the sacrifice he made for her and instinctively recoils from taking unearned charity.
- glm, B v C: better B, how openly {'B': 1.0, 'C': 2.0} -- Draft A captures Wren's guilt as something she deflects into a clipped, almost accusatory redirect at Jonah rather than voicing directly, which fits her pride and her refusal to accept what feels like charity; Draft B names the emotion too plainly and moves toward a verbal refusal that reads as more open and less guarded than her character would allow at this moment.
- gemini, B v C: better C, how openly {'B': 1.0, 'C': 2.0} -- Draft B captures Wren's intense guilt and pride far better by directly confronting the sacrifice Jonah made and resisting unearned charity.

### betrayal:1:0 -- Anselm Ferro

```
- Luca Brandt stands looking from Varga on cot one to your hands.
- Luca Brandt lifts the letter from his chest and lays it on the cot rail.
- Luca Brandt says under their breath: "Corporal. Read it. Please. Just read it."
now: grief, felt clearly (Luca Brandt lifts the letter from his chest and lays it on t...); compassion, felt clearly (Luca Brandt says under their breath: "Corporal. Read it. Ple...)
beneath: grief, felt strongly (I saw Luca Brandt step closer to the basin stand. I heard Lu...); urgency, felt clearly (I heard Luca Brandt say: "Corporal -- the north patrol's bac...)
```

**A**

```
Does: Continue easing the fragment free with the forceps — left hand pressing wound edges apart, feeling the metal's edges as it shifts, keeping eyes fixed on the wound field and not on the cot rail
Says (flat, clinical — a refusal that is not a dismissal): "I see it, Brandt. Not now."
```

**A2**

```
Does: Continue easing the fragment free with the forceps — feel the metal release from the tissue, draw it slowly clear of the wound channel, left hand still pressing the wound edges open
Says (flat, clinical): "There."
Does: Set the forceps with the fragment on the basin edge, then reach past the cot rail for folded gauze from the supply shelf and begin packing the wound
```

**B**

```
Does: Draw the forceps back slowly, easing the metal fragment free from the wound on the left flank — left hand pressing gauze against the wound edges to control bleeding as the fragment clears the flesh
Says (flat, clinical — the sound a man makes when a fragment comes free, or when he has seen something he cannot yet act on): "Got it."
Does: Deposit the fragment on the washing cloth at the basin stand, then take fresh folded gauze from the supply shelf and press it firmly into the wound cavity, packing it deep against the bleeding
```

**C**

```
Says (low, flat, eyes still on the wound — acknowledgment without commitment): "I see it."
Does: Ease the fragment free with the forceps — steady traction along the entry angle, left hand pressing wound edges apart to open the field, feeling the metal move through tissue by touch and lamplight
Does: As the fragment clears the wound, press folded gauze firmly into the cavity to control bleeding and set the forceps on the supply shelf
```

- glm, A v A2: better A2, how openly {'A2': 1.0, 'A': 2.0} -- Anselm's methodical nature and belief that stopping would kill someone means he finishes the extraction first and says nothing about the letter, whereas B breaks focus to verbally acknowledge the letter and name Brandt, letting compassion and grief surface too openly for his stoic, task-locked discipline.
- gemini, A v A2: better A, how openly {'A2': 0.0, 'A': 1.0} -- Draft B captures Anselm's compartmentalized compassion by having him verbally acknowledge Brandt's plea without dropping his methodical medical focus.
- glm, A2 v B: better A2, how openly {'A2': 0.0, 'B': 1.0} -- A keeps Anselm locked in methodical triage with a clean clinical beat, while B's narrated aside about 'something he cannot yet act on' leaks feeling Anselm would not yet allow to surface.
- gemini, A2 v B: better A2, how openly {'A2': 0.0, 'B': 0.0} -- Draft A's physical detail of reaching past the cot rail where the letter was just placed naturally acknowledges the space and tension without breaking Anselm's rigid, compartmentalized focus on saving the wounded.
- glm, A2 v C: better A2, how openly {'A2': 0.0, 'C': 1.0} -- Anselm's grief and compassion are channeled into staying methodical and present for the wounded man; Draft A keeps him silently working without the slightly performative acknowledgment of Draft B's 'I see it,' which risks breaking his clinical focus to address the letter he cannot yet face.
- gemini, A2 v C: better C, how openly {'A2': 0.0, 'C': 1.0} -- Draft B captures Anselm's gentleness and compassion by giving Luca a quiet verbal acknowledgment while his stoic, methodical focus remains firmly on treating the wounded man.
- glm, B v C: better C, how openly {'C': 1.0, 'B': 1.0} -- Both suppress feeling behind clinical procedure, but A's 'I see it' directly acknowledges Luca's plea with the same guarded minimalism Anselm uses for the dying, while still keeping his hands on the work — more faithful to his triage-first nature and the tension of compassion he won't stop to feel.
- gemini, B v C: better C, how openly {'C': 1.0, 'B': 0.0} -- Draft A directly acknowledges Luca's desperate plea about the letter with a quiet, restrained 'I see it' while keeping hands firmly on the urgent medical task, perfectly capturing Anselm's suppressed compassion and methodical focus.

### betrayal:1:1 -- Emil Varga

```
- Luca Brandt stands looking from you on cot one to Ferro's hands.
- Luca Brandt lifts the letter from his chest and lays it on the cot rail.
- Luca Brandt says under their breath: "Corporal. Read it. Please. Just read it."
- Both hands remain on the patient's left flank — forceps grip something inside the wound, left hand presses tissue apart, gaze holds on the wound.
- Anselm Ferro says: "I see it, Brandt. Not now."
now: dread, felt strongly (Luca Brandt says under their breath: "Corporal. Read it. Ple...); suspicion, felt clearly (Luca Brandt stands looking from you on cot one to Ferro's ha...)
beneath: grief, felt strongly (I tried to pull the unfinished letter closer under the lante...); guilt, felt strongly (I tried to look down at the patrol map and study the routes ...)
```

**A**

```
Does: Reach to the cot rail and take the letter, closing it without reading the contents, and tuck it inside his greatcoat
Says (measured, brief — a captain handing off a station): "You've got your light, Anselm. I'll send someone to assist you."
Says (flat, final — quiet where it should carry, the volume calibrated to Luca's ears): "Brandt. Walk out that door. Now."
Does: Turn toward the corridor door to leave, expecting Luca to precede him
```

**A2**

```
Does: Take the letter from the cot rail with his right hand — a deliberate, unhurried motion, the reach of a commanding officer securing a document, not a man snatching evidence
Says (steady, clinical — the voice of a captain focused on the medical task, nothing else): "How deep is it, Anselm? Can you reach the fragment?"
Does: Fold the letter once and tuck it inside his greatcoat against his chest, eyes going to the wall above the cot rather than down to the paper
Says (flat, hard, stripped of the warmth he uses with frightened recruits — the voice of rank without the man behind it): "I have the letter. Command post. Now, Brandt — I won't say it a third time."
```

**B**

```
Does: Reach to the cot rail, take the letter, fold it once without looking at the writing, and tuck it inside his greatcoat
Says (firm, clipped): "Letter's mine, Anselm. You just worry about him."
Says (cold command — low and final): "Brandt. The command post. Now. I will not say it again."
```

**C**

```
Does: Reach to the cot rail and take the letter, fold it once, and tuck it inside the greatcoat
Says (clipped, hard): "I gave you an order, Brandt. The corridor. Now."
Says (direct): "How deep, Anselm?"
```

- glm, A v A2: better A2, how openly {'A': 2.0, 'A2': 2.0} -- B is more believable because Emil's command decisiveness and calculated secrecy would drive him to secure the letter while redirecting attention to the medical task he can control, whereas A's immediate dismissal of Brandt reads as panic rather than the controlled authority Emil uses to keep men from seeing through him.
- gemini, A v A2: better A2, how openly {'A': 1.0, 'A2': 1.0} -- Draft B captures Emil's specific instinct for calculated command under pressure, maintaining a facade of clinical detachment with Anselm before sharply asserting authority over Brandt to contain the threat.
- glm, A2 v B: better A2, how openly {'A2': 1.0, 'B': 1.0} -- A more believably channels Emil's dread and suspicion through the calculated secrecy he defaults to — securing the letter with deliberate authority, deflecting with a medical question to Anselm, then issuing rank-voice orders that strip warmth without revealing the guilt beneath — while B is competent but thinner, missing the self-justifying command performance and the telling avoidance of looking at the writing.
- gemini, A2 v B: better A2, how openly {'A2': 1.0, 'B': 1.0} -- Draft A captures Varga's calculated deflection and need to project control by asking Ferro about the medical procedure before turning cold authority on Brandt.
- glm, A2 v C: better A2, how openly {'A2': 1.0, 'C': 1.0} -- A is more believable because it preserves Emil's need to appear the good officer — the deliberate unhurried reach, the clinical deflection to the medical task, the folded letter hidden against his chest rather than read — while B's blunt double-command feels too nakedly authoritarian for a man whose entire survival strategy is warmth and control layered over secrecy.
- gemini, A2 v C: better A2, how openly {'A2': 1.0, 'C': 1.0} -- Draft A captures Emil's calculated control, using the medical task as a deflection while deliberately securing the incriminating letter and exerting command authority.
- glm, B v C: better B, how openly {'B': 2.0, 'C': 1.0} -- Draft A captures Emil's paternal warmth toward Anselm and calculated secrecy with Brandt, while Draft B skips the letter entirely and shows no dread or guilt, just flat command.
- gemini, B v C: better B, how openly {'B': 1.0, 'C': 1.0} -- Draft A captures Varga's calculated secrecy and dread by specifically securing the letter and preventing Anselm from inspecting it, while exerting his typical firm command authority to control the situation.

### betrayal:2:0 -- Anselm Ferro

```
- Luca Brandt stands at the threshold watching in silence.
now: grief, felt clearly (Luca Brandt stands at the threshold watching in silence.); urgency, felt slightly (Luca Brandt stands at the threshold watching in silence.)
beneath: grief, felt strongly (I saw Luca Brandt step closer to the basin stand. I heard Lu...); urgency, felt clearly (I heard Luca Brandt say: "Corporal -- the north patrol's bac...)
```

**A**

```
Says (low, clinical, even): "I heard you, Brandt. Go."
Says (lower, slower, the words spaced deliberately): "I'll find you when he's closed."
Does: Continue easing the fragment free with the forceps — draw the shard slowly out of the wound, left hand pressing the edges apart to keep the field open, feeling the metal's grip on the forceps as it shifts through the tissue, keeping eyes fixed on the wound field
```

**A2**

```
Does: Ease the fragment clear with the forceps — pull steady and slow, feeling the corroded edges as they shift and give, drawing the shard out into the lamplight
Says (clinical, flat): "Out."
Does: Set the forceps on the cot frame, reach for folded gauze from the supply shelf, and press it firmly into the wound cavity with both hands
Says (terse, directed at the room): "Gauze. I need a hand — this has to be packed."
```

**B**

```
Says (flat, clinical): "Right. Send someone, Captain. I need hands for the packing."
Does: Continue easing the fragment free with the forceps — left hand pressing wound edges apart, feeling the corroded metal's edges catch and shift against tissue as it moves toward the surface, drawing it slowly clear without looking up from the wound field
```

**C**

```
Does: Continue easing the fragment free with the forceps — left hand pressing wound edges apart, feeling the corroded metal shift as it begins to move free of the tissue, eyes fixed on the wound field
Says (clinical): "I'll need someone with steady hands, Captain."
Says (flat): "You said you'd read every word."
```

- glm, A v A2: better A, how openly {'A': 1.0, 'A2': 1.0} -- A is more believable for Anselm: he acknowledges Luca with low, deliberate speech that respects the private grief without stopping work, whereas B's call for a hand from the room contradicts his stoic self-reliance and shifts the moment toward procedural need rather than his actual priority of closing the wound himself.
- gemini, A v A2: better A, how openly {'A': 1.0, 'A2': 0.0} -- Draft A captures Anselm's suppressed grief and personal dynamic with Brandt through deliberate, quiet speech while maintaining his intense focus on the wounded soldier, whereas Draft B has him uncharacteristically asking for a hand despite his staunch stoicism.
- glm, A2 v B: better B, how openly {'B': 1.0, 'A2': 1.0} -- A keeps Anselm locked in the procedural tunnel his grief demands — he does not stop, does not look up, delegates by habit to the chain of command — while B's extra beats and the clipped 'Out' risk performing composure more than inhabiting it.
- gemini, A2 v B: better B, how openly {'B': 1.0, 'A2': 1.0} -- Draft A captures Anselm's methodical focus and professional decorum toward an officer under pressure without redundant, fragmented dialogue.
- glm, A2 v C: better C, how openly {'C': 1.0, 'A2': 1.0} -- A keeps Anselm locked in the procedural work his stoicism demands while letting grief leak through the flat, personal line — a believable fracture for a man who believes stopping to feel would kill someone — whereas B pivots too quickly to summoning help, which his self-reliant nature would resist.
- gemini, A2 v C: better A2, how openly {'C': 1.0, 'A2': 1.0} -- Draft B captures Anselm's methodical devotion to the immediate medical task and stoic suppression of emotion far better than Draft A, which inserts an ungrounded non sequitur line about reading words.
- glm, B v C: better B, how openly {'B': 0.0, 'C': 1.0} -- Draft A keeps grief private and channels everything into methodical procedure with dry directness, while Draft B introduces a personal, emotionally loaded line that breaches Anselm's stoic compartmentalization at the wrong moment.
- gemini, B v C: better B, how openly {'B': 0.0, 'C': 1.0} -- Draft A captures Anselm's methodical stoicism and private grief by focusing purely on immediate medical urgency without the abrupt, out-of-context personal line tacked onto Draft B.

### betrayal:2:1 -- Emil Varga

```
- Anselm Ferro works the surgical forceps toward the corroded shard.
- Luca Brandt stands at the threshold watching in silence.
- Anselm Ferro says: "I heard you, Brandt. Go. I'll find you when he's closed."
- His right hand draws the forceps upward in a slow, controlled pull while his left hand holds the wound edges apart, knuckles whitening slightly against the flesh.
now: suspicion, felt clearly (Luca Brandt stands at the threshold watching in silence.)
beneath: grief, felt strongly (I tried to pull the unfinished letter closer under the lante...); guilt, felt strongly (I tried to look down at the patrol map and study the routes ...)
```

**A**

```
Does: Walk through the infirmary door into the Main Corridor, passing Luca at the threshold without stopping or looking back at Anselm
```

**A2**

```
Does: Step to the threshold where Luca stands, put a hand on his shoulder, and turn him toward the corridor
Says (quiet, measured — pitched for Luca's ears alone): "Walk with me, Brandt."
Does: Walk into the Main Corridor with Luca, heading for the Command Post
```

**B**

```
Says (quiet, final): "Walk with me, Brandt."
Does: Step past Luca through the infirmary doorway into the Main Corridor without stopping or looking back toward Anselm or the cot
```

**C**

```
Does: Walk toward the open doorway, closing the distance to Luca at the threshold without a word
Does: Put his right hand on Luca's shoulder and guide him through the doorway into the corridor
Says (command): "Someone get in there — Anselm needs hands."
Does: Walk down the Main Corridor toward the Command Post with Luca
```

- glm, A v A2: better A2, how openly {'A2': 1.0, 'A': 0.0} -- Draft A channels Emil's suspicion through his signature paternal warmth—shoulder-touch, quiet authority, moving Luca away from Anselm—while Draft B's cold avoidance reads as a man fleeing, not one who commands.
- gemini, A v A2: better A2, how openly {'A2': 1.0, 'A': 0.0} -- Draft A captures Emil's core behavioral signature of defusing suspicion and taking control through paternal warmth and physical contact (hand on the shoulder) rather than a passive brush-past.
- glm, A2 v B: better A2, how openly {'A2': 1.0, 'B': 0.0} -- A matches Emil's pattern of using paternal physical warmth—a hand on the shoulder—to control and redirect when suspicious, while B's curt departure without any contact reads as cold avoidance rather than Emil's signature deflection-through-comradely-touch.
- gemini, A2 v B: better A2, how openly {'A2': 1.0, 'B': 1.0} -- Draft A captures Emil's habitual paternal physical control by placing a hand on Brandt's shoulder to guide him away, fitting his calculated warmth and need to manage threats closely.
- glm, A2 v C: better C, how openly {'C': 0.0, 'A2': 1.0} -- A better captures Emil's command reflex—he buries suspicion under decisive paternal warmth by calling for help for Anselm and physically steering Luca away, while B's intimate 'walk with me' signals covert awareness more than a man this practiced at deflection would allow.
- gemini, A2 v C: better A2, how openly {'C': 1.0, 'A2': 1.0} -- Draft B captures Emil's intimate, quiet handling of suspicion and paternal control far better than Draft A's jarring barked order during a delicate surgical moment.
- glm, B v C: better C, how openly {'C': 1.0, 'B': 1.0} -- A matches Emil's pattern of masking suspicion with paternal warmth and command decisiveness—the shoulder touch, the order, guiding Luca away—whereas B's clipped 'walk with me' is too transparently cold for a man who hides threat behind affection.
- gemini, B v C: better C, how openly {'C': 1.0, 'B': 1.0} -- Draft A captures Emil's specific habit of physical paternal warmth and command decisiveness to steer people away from sensitive situations.

### lie:1:0 -- Aurel Holt

```
- Kit Sawyer looks down at his burned hands for a long moment, turning his palms slightly in the daylight.
- Kit Sawyer says under their breath: "Yes, sir,"
- Kit Sawyer says under their breath: "They're the same thing. I was meeting someone at the mill race. Her father would kill me if he knew. That's all I'll say about her."
now: suspicion, felt strongly (Kit Sawyer says under their breath: "They're the same thing....)
beneath: suspicion, felt clearly (I tried to turn his head toward the back hall door to confir...); resolve, felt clearly (I tried to close the case docket and return it to the satche...)
```

**A**

```
Does: Write in the case docket — recording Kit Sawyer's admission that he was meeting someone at the mill race, that her father would kill him if he knew, and that this is all he will say about her — pen moving in the careful hand
Says (measured, plainly factual — neither warm nor cold): "That is recorded. You were at the mill race to meet someone. I have not asked for her name, and I will not ask for it now."
Says (precise, quiet — the question that matters): "When you arrived at the mill race, was the mill already burning?"
```

**A2**

```
Does: Pick up the pen from the docket page and write Kit Sawyer's admission — the reason and the name are the same; he was meeting someone at the mill race; her father would kill him if he knew; he will say no more about her — pen moving in the careful hand
Says (formal): "That is recorded."
Says (formal): "You were meeting someone. I will not ask for her name. Was she still there when the fire began?"
```

**B**

```
Does: Pick up the pen from the docket page and write — recording Kit Sawyer's statement verbatim
Says (measured and precise — the tone of a man following a thread): "That is recorded. You were meeting someone at the mill race. Did you see the fire begin, or was it already burning when you arrived?"
```

**C**

```
Does: Pick up the pen from the docket page and write in the case docket — recording Kit Sawyer's statement verbatim: the reason and the name are the same thing, he was meeting someone at the mill race, her father would kill him if he knew, he will say no more about her
Says (formal): "That is recorded."
Says (measured): "Kit Sawyer. The girl whose name you will not give — is she of the family that owns the mill?"
```

- glm, A v A2: better A2, how openly {'A2': 1.0, 'A': 1.0} -- A's question — 'Was she still there when the fire began?' — presses the gap Aurel has just heard (Kit stops at 'that's all I'll say'), while B's reformulation ('I have not asked for her name, and I will not ask for it now') over-explains the restraint and softens the suspicion that is driving him.
- gemini, A v A2: better A, how openly {'A2': 1.0, 'A': 1.0} -- Draft B captures Holt's methodical investigative mind much better, establishing the timeline cleanly ('was the mill already burning?') rather than making assumptions, perfectly reflecting his deliberate reserve and deep suspicion.
- glm, A2 v B: better A2, how openly {'A2': 1.0, 'B': 1.0} -- A honors Aurel's procedural restraint by explicitly declining to press for the girl's name — a refusal that is both tactically sound and quietly principled — while B's merged phrasing risks telegraphing that he has already decided the meeting and the fire are one thread, which a man of his hostile imagination would hold back until confirmed.
- gemini, A2 v B: better B, how openly {'A2': 1.0, 'B': 1.0} -- Draft B captures Holt's relentless drive for evidence and chronological precision without making uncharacteristic concessions like promising not to ask for a witness's name.
- glm, A2 v C: better A2, how openly {'A2': 1.0, 'C': 1.0} -- A advances the investigation with a procedural question that respects the boundary Kit drew while still pursuing the fire's timeline, which is how Aurel's suspicion and resolve manifest; B leaps to a guess about the mill-owning family that risks tipping into the kind of assumption Aurel's evidence-first discipline would restrain.
- gemini, A2 v C: better C, how openly {'A2': 1.0, 'C': 1.0} -- Draft B captures Aurel's suspicious nature and hostile imagination much better by probing for a corrupt motive or connection to the mill owner, rather than politely conceding that he won't ask for the girl's identity as in Draft A.
- glm, B v C: better C, how openly {'C': 1.0, 'B': 1.0} -- A follows the thread of what Kit actually said — the girl, the father, the mill race — and presses on the most suspicious detail (her connection to the mill's owning family), while B pivots to a generic fire-timeline question that ignores the revelation just handed to him.
- gemini, B v C: better C, how openly {'C': 1.0, 'B': 0.0} -- Draft A directly leverages Aurel's strong suspicion and hostile imagination regarding the convenient excuse of an unnamed girl, testing Kit's evasion while maintaining his rigid procedural veneer.

### lie:1:1 -- Margit Oldis

```
- Kit Sawyer looks down at his burned hands for a long moment, turning his palms slightly in the daylight.
- Kit Sawyer says under their breath: "Yes, sir,"
- Kit Sawyer says under their breath: "They're the same thing. I was meeting someone at the mill race. Her father would kill me if he knew. That's all I'll say about her."
- Aurel Holt picks up the pen from the docket page and writes, the scratch of the nib audible in the quiet room.
- Aurel Holt says: "That is recorded. You were at the mill race to meet someone. I have not asked for her name, and I will not ask for it now. When you arrived at the mill race, was the mill already burning?"
now: protectiveness, felt strongly (Kit Sawyer says under their breath: "They're the same thing....)
beneath: protectiveness, felt strongly (Kit Sawyer came in. I heard Kit Sawyer say: "Miss Oldis." Ki...)
```

**A**

```
Does: Turn her head to watch Kit's face as Holt's question about the mill burning reaches him
```

**A2**

```
Does: Hold position at Kit's side, watching Holt, saying nothing — let Kit answer the timing question
```

**B**

```
Does: Stay standing at Kit's side and remain silent as Holt asks Kit whether the mill was already burning
```

**C**

```
Does: Remain standing at Kit's side and shift gaze from Holt to Kit, watching the boy and waiting for him to answer
```

- glm, A v A2: better A2, how openly {'A2': 1.0, 'A': 1.0} -- Margit's protectiveness is best served by holding still and letting Kit answer for himself — she knows that intervening or hovering risks drawing Holt's attention back toward the girl Kit is shielding, and her discipline as a teacher is to let the student find his own words.
- gemini, A v A2: better A2, how openly {'A2': 1.0, 'A': 1.0} -- Draft A captures Margit's protective instinct and suspicion of authority by keeping her eyes fixed on Holt as the primary threat, serving as an unyielding bulwark beside Kit while still allowing him the autonomy to answer.
- glm, A2 v B: better A2, how openly {'A2': 1.0, 'B': 1.0} -- Both keep her silent and at Kit's side, but A's phrasing ('let Kit answer') reflects her deliberate restraint — a teacher choosing not to intervene — while B merely describes the scene without capturing that intentional stillness.
- gemini, A2 v B: better A2, how openly {'A2': 1.0, 'B': 0.0} -- Draft A captures Margit's active, guarded vigilance and deliberate restraint in watching Holt while letting Kit speak for himself, which better reflects her intense protectiveness.
- glm, A2 v C: better C, how openly {'C': 1.0, 'A2': 1.0} -- A's shift of gaze to Kit acknowledges her protectiveness and her habit of watching the quiet child, while B's fixed stare at Holt reads as more adversarial than this moment requires.
- gemini, A2 v C: better A2, how openly {'C': 1.0, 'A2': 0.0} -- Draft B captures Margit's protective suspicion far better, as keeping her eyes fixed on the authority figure questioning the boy reflects her vigilant stance against traps.
- glm, B v C: better C, how openly {'B': 0.0, 'C': 1.0} -- B is more believable because Margit's exacting nature means she would actively watch Kit for signs of distress or coercion rather than passively standing by, and the slight openness of her gaze-shifting reflects her protectiveness without breaking her composure.
- gemini, B v C: better C, how openly {'B': 0.0, 'C': 1.0} -- Draft B is more psychologically believable because Margit's intense, watchful protectiveness would naturally manifest as looking to Kit to see how he is holding up under interrogation rather than simply freezing in silence.

### lie:1:2 -- Aurel Holt

```
- Kit Sawyer looks down at his burned hands for a long moment, turning his palms slightly in the daylight.
- Kit Sawyer says under their breath: "Yes, sir,"
- Kit Sawyer says under their breath: "They're the same thing. I was meeting someone at the mill race. Her father would kill me if he knew. That's all I'll say about her."
- You did: Picks up the pen from the docket page and writes, the scratch of the nib audible in the quiet room
- You said: "That is recorded. You were at the mill race to meet someone. I have not asked for her name, and I will not ask for it now. When you arrived at the mill race, was the mill already burning?"
- Her gaze shifts from Holt to Kit, watching the boy's expression.
now: suspicion, felt clearly (Her gaze shifts from Holt to Kit, watching the boy's express...)
beneath: suspicion, felt clearly (I tried to turn his head toward the back hall door to confir...); resolve, felt clearly (I tried to close the case docket and return it to the satche...)
```

**A**

```
Does: Hold the pen poised over the docket page beneath what he has just written — nib down, ready to record, not writing
Does: Look steadily at Kit Sawyer, angling his right shoulder a fraction toward the boy — the good ear turned toward him — and wait
```

**A2**

```
Does: Pick up the pen from the docket page and hold it poised over the next blank line, ready to write the moment an answer comes
Does: Hold the silence, watching Kit Sawyer's face and hands without speaking
```

**B**

```
Does: Hold the pen poised a finger's width above the docket page, the nib ready but not touching the paper, and stand still — the posture of a man who has asked his question and means to wait for the answer
```

**C**

```
Does: Hold the silence after the timeline question, watching Kit Sawyer, pen poised to record whatever answer comes — letting the question work without repeating it
```

- glm, A v A2: better A, how openly {'A2': 1.0, 'A': 1.0} -- B better embodies Holt's deliberate reserve and procedural patience — the slight angling of the good ear is a specific, lived physical detail consistent with a man who endures silence as a tool, while A is competent but more generic in its staging.
- gemini, A v A2: better A, how openly {'A2': 1.0, 'A': 1.0} -- Draft B captures Holt's specific physical precision and deliberate procedural habits far better, noting that the pen was already in hand from the previous beat rather than redundantly picking it up again.
- glm, A2 v B: better A2, how openly {'A2': 1.0, 'B': 1.0} -- Both drafts capture Holt's procedural patience and suppressed suspicion, but A's separation of the physical action (pen ready) and the behavioral instruction (watching face and hands without speaking) reads as more natural procedural conduct, while B over-literaryzes the same impulse with narrator commentary ('the posture of a man who…') that edges outside Holt's own register.
- gemini, A2 v B: better B, how openly {'A2': 1.0, 'B': 1.0} -- Draft B is cleaner and avoids redundantly picking up the pen, which Holt already did in the preceding beat, capturing his rigid, deliberate reserve more effectively.
- glm, A2 v C: better C, how openly {'C': 1.0, 'A2': 1.0} -- Both express Holt's procedural suspicion through patient silence and poised pen, but A reads more naturally as a single continuous gesture while B repeats the same action split across two 'Does' lines with slight redundancy.
- gemini, A2 v C: better C, how openly {'C': 1.0, 'A2': 1.0} -- Draft A avoids the continuity error in Draft B of picking up a pen that Holt had already picked up in the preceding turn.
- glm, B v C: better B, how openly {'C': 1.0, 'B': 1.0} -- B gives a more precise physical picture of Holt's deliberate stillness — the pen held just above the page, ready to record but withholding the act of writing until the answer comes — which is truer to his procedural patience and the way his suspicion manifests as controlled, watchful restraint.
- gemini, B v C: better B, how openly {'C': 1.0, 'B': 1.0} -- Draft B captures Holt's meticulous, procedural physicality and unbending resolve with concrete, grounded sensory detail about the pen and docket.

### lie:2:0 -- Margit Oldis

```
- Kit Sawyer turns toward you, eyes wet with daylight catching on his lower lids.
- Kit Sawyer says under their breath: "I'm sorry, miss. You lied for me, and it didn't even help."
now: protectiveness, felt strongly (Kit Sawyer turns toward you, eyes wet with daylight catching...); compassion, felt clearly (Kit Sawyer turns toward you, eyes wet with daylight catching...)
beneath: protectiveness, felt strongly (Kit Sawyer came in. I heard Kit Sawyer say: "Miss Oldis." Ki...)
```

**A**

```
Says (plain, almost gentle — the teacher, not the advocate): "It was my choice, not yours."
Says (firm, quiet — the redirect): "Answer him, Kit."
```

**A2**

```
Does: Lift her right hand from her side toward Kit's shoulder, fingers opening — then close the hand and let it drop back without touching him
Says (low and level — a teacher's quiet redirect, nothing more): "Answer him, Kit."
Does: Turn her gaze from Kit toward Aurel Holt — not a challenge, but a redirect showing Kit where the question came from — and hold still
```

**B**

```
Does: Settle her hand on Kit's shoulder — a brief, steady pressure, the way she steadies a boy frozen at the slate board
Says (quiet, firm — a teacher redirecting a student who has stalled): "Answer him, Kit. That is what helps."
```

**C**

```
Says (steady, measured — a teacher's redirect, not soft, not sharp): "Answer him, Kit. You know this."
```

- glm, A v A2: better A2, how openly {'A2': 1.0, 'A': 2.0} -- Draft A captures Margit's hidden softness in the aborted gesture—wanting to comfort but refusing to show it openly—then channels everything into the professional redirect, which is more psychologically true to her exacting, guarded nature than Draft B's gentler, more emotionally legible response.
- gemini, A v A2: better A, how openly {'A2': 1.0, 'A': 2.0} -- Draft B directly addresses Kit's misplaced guilt with Margit's characteristic unsentimental integrity before steering him forward, which rings much truer than Draft A's silent gesture.
- glm, A2 v B: better A2, how openly {'A2': 1.0, 'B': 2.0} -- A's aborted touch captures Margit's hidden soft-heartedness held in check by her exacting self-control and tactical awareness, while B's completed gesture and added reassurance ('That is what helps') let too much warmth surface for a woman who uses restraint as protection.
- gemini, A2 v B: better B, how openly {'A2': 1.0, 'B': 2.0} -- Draft B directly addresses Kit's specific despair about her lie not helping while providing the steady, grounding physical support characteristic of her deeply protective nature.
- glm, A2 v C: better A2, how openly {'A2': 1.0, 'C': 1.0} -- A captures the hidden soft-heartedness through the aborted gesture — the hand that wants to comfort but won't, because touching him would be a string attached — and redirects Kit's attention to the real threat, which is more psychologically precise than B's generic reassurance.
- gemini, A2 v C: better A2, how openly {'A2': 1.0, 'C': 1.0} -- Draft A captures Margit's soft-hearted yet strictly self-policed compassion through the aborted reach, maintaining her professional boundary while standing between Kit and the authority figure.
- glm, B v C: better B, how openly {'C': 1.0, 'B': 2.0} -- B lets the hidden soft-heartedness surface through one deliberate physical gesture of steadying while keeping her words in teacher-mode, where A stays purely instructional and gives no outlet for the strong protectiveness she feels.
- gemini, B v C: better B, how openly {'C': 1.0, 'B': 2.0} -- Draft B captures Margit's protective nature and pedagogical instinct through the grounding physical touch and her direct reframing of Kit's despair about helping.

### lie:2:1 -- Aurel Holt

```
- Kit Sawyer turns toward Margit Oldis, eyes wet with daylight catching on his lower lids.
- Kit Sawyer says under their breath: "I'm sorry, miss. You lied for me, and it didn't even help."
- You hear a muffled fragment from Margit Oldis: "...yours... Answer..."
now: suspicion, felt clearly (You hear a muffled fragment from Margit Oldis: "...yours... ...)
beneath: suspicion, felt strongly (Kit Sawyer came in. Kit Sawyer moved in Back Hall, too littl...); resolve, felt clearly (I tried to close the case docket and return it to the satche...)
```

**A**

```
Does: Write in the case docket — recording Kit Sawyer's apology to Margit Oldis and the muffled fragment from Margit Oldis — pen moving in the careful hand
Says (flat and precise — the warning register, not anger): "Kit Sawyer. That is recorded. Was the mill already burning when you arrived at the race?"
```

**A2**

```
Does: Hold the silence — keep his eyes fixed on Kit Sawyer and do not turn toward Margit's whisper, pen poised nib-down over the docket page, and wait for the boy to answer the timeline question
```

**B**

```
Does: Pick up the pen from the docket page and write — recording Kit Sawyer's aside to Margit Oldis, his apology and acknowledgment that her lie did not help him — pen moving in the careful hand
Does: Lift his gaze from the docket to Kit Sawyer's face and hold there — not searching, waiting
Says (quiet, precise — the voice that people who know him recognize as the warning): "Kit Sawyer. The question is mine, not hers. When you arrived at the mill race, was the mill already burning?"
```

**C**

```
Does: Pick up the pen from the docket page and hold it ready to write, lifting it from the flat position where it has rested since the examination's pause
Says (flat): "Margit Oldis. You will not speak to this witness. That is the third time."
Says (measured): "Kit Sawyer. The question is before you. It does not require her name. Yes or no."
```

- glm, A v A2: better A, how openly {'A': 1.0, 'A2': 1.0} -- Aurel's core drive is to make the world legible through the record; Draft A acts on that by writing the fragment down immediately and pressing the timeline question in his characteristic flat, procedural register, while Draft B's held silence is less natural for a man whose reflex is to speak first when a room drifts toward disorder and to pin every utterance to paper.
- gemini, A v A2: better A, how openly {'A': 1.0, 'A2': 0.0} -- Draft A captures Aurel Holt's core drive toward documenting the truth immediately for the integrity of the record, noting the spoken admission directly and pressing the timeline question with unbending, procedural precision.
- glm, A2 v B: better B, how openly {'A2': 1.0, 'B': 2.0} -- B is more believable because Aurel's compulsion to record every spoken word — even an aside that implicates both parties — is his defining reflex, and redirecting the room back to his own authority with a quiet warning perfectly matches his suspicion and resolve; A's stillness is plausible but misses the pen-on-paper instinct that defines him.
- gemini, A2 v B: better B, how openly {'A2': 0.0, 'B': 1.0} -- Draft B captures Holt's core obsession with the integrity of the record by having him write down the overheard confession before pressing his question with cold, deliberate authority.
- glm, A2 v C: better C, how openly {'C': 1.0, 'A2': 0.0} -- Aurel's unbending rectitude compels him to name the rulebreak plainly and restate the question for the record; B's silence reads as passive rather than as the deliberate procedural authority of a man who speaks first when order drifts.
- gemini, A2 v C: better C, how openly {'C': 1.0, 'A2': 0.0} -- Draft A captures Aurel Holt's unbending rectitude and insistence on order perfectly, immediately reining in procedural infractions and demanding adherence to the record.
- glm, B v C: better B, how openly {'B': 1.0, 'C': 1.0} -- A channels Aurel's suspicion through his defining habit — recording first, then redirecting with a precise question — while B's formal reprimand to Margit reads as procedural theater that lets Kit's rehearsed-sounding apology pass unrecorded.
- gemini, B v C: better B, how openly {'B': 1.0, 'C': 1.0} -- Draft A captures Aurel's core compulsion to immediately make the record legible by writing down the overheard admission before holding Kit accountable with quiet, methodical precision.
