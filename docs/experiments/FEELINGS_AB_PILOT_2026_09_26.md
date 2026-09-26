# Feelings A/B: a pilot on six replayed beats

Status: EVIDENCE, 2026-09-26. Instrument: `tools/feelings_ab.py`. Design
context: [`DESIGN_JEV_CHARACTER_PASS.md`](../design/DESIGN_JEV_CHARACTER_PASS.md),
"Wiring the affect pass"; the naming it compares:
[`JEV_MEMORY_PROBE_2026_09_26.md`](JEV_MEMORY_PROBE_2026_09_26.md), "Round
seven".

**The question.** Does a character act better for being handed its feelings,
and for being handed them named well? 23 captured `character_major` calls in
the four test stories carry a `self.feelings` block (the turns the affect pass
ran on). Each was to be answered again three ways -- the system prompt and
payload as captured but for the block: `none` (removed), `old` (as captured,
named by OCC's rules of that turn: "satisfaction" as a rival hands over a
printed proof, "anger (someone)"), `new` (`now` and `beneath` named by today's
direct question from the same inputs, the captured mood words kept) -- on the
stories' own route (GLM 5.2, OpenRouter). Two blind judges (GLM 5.2 and Gemini
3.8 Flash as the `utility` role) compared two answers of a beat at a time, in
a random order, on conduct alone.

**The pilot: six beats, 18 answers, 36 verdicts.** All 18 answers validated;
calls took 22-200 s.

| pair | GLM judge | Gemini judge | both agree |
|---|---|---|---|
| none against old | 3 : 3 | 3 : 3 | 2 : 2 |
| none against new | 2 : 4 | 3 : 3 | 2 : 3 |
| old against new | 4 : 2 | 2 : 4 | 2 : 2 |

Neither judge ever answered "same", and each judge's "in which do the
feelings come through more" followed its "better" on every pair. The judges
argue from substance ("not rough, not gentle, just done" against "gently but
firmly"; playing the piece against explaining it), but what they weigh is the
sampling variation between two calls, not the block: the character's drive
and situation carry its conduct, and the feelings tint its lines -- in every
arm Isolde reads her printed name and demands the notation; in every arm Wren
pulls her hand free and reads the card.

**Why it stopped at six.** The effect is under the noise between two calls of
one arm, so the remaining 17 beats (about $2.50 of character calls and $0.50
of judging, on the owner's OpenRouter route, with the balance at $21.47)
would not resolve it. A design that could -- the same arm twice for a noise
floor, several samples per beat -- costs several times more; it is the
owner's call. What the pilot does show: the block does not destabilise
conduct, and swapping OCC's misnamed feelings for the direct question's did
not visibly move it either way at this size.

## The pairs, side by side

The judges' reasons follow each beat; "A" and "B" in them are the order the
judge saw, not the arm names.

## rival:203 -- Isolde Varga, turn 21

```
THE CHARACTER: Isolde Varga.
WHAT DRIVES YOU: To write one piece of music that will still be sung after everyone who knew her is dead. Works the craft daily whether or not inspiration arrives; hoards and polishes themes across years; keeps a private folio of unfinished fragments she believes are her best; measures every commission against that standard; when a rehearsal stalls, she is the one who says what the next step is and makes it happen.
WHAT YOU VALUE, MOST FIRST: Craft over inspiration; Loyalty to the house over personal ambition; Privacy of feeling over risking the friendship; Generosity to the young over self-protection; Fairness in credit over advantage
HOW YOU ARE: Disciplined diligence -- Writes four hours before noon even after a performance night; keeps the house's score library in order without being asked; turns up ea...; Watchful envy -- Quietly catalogs who received which praise and for what; goes cool and precise with anyone whose talent seems to cost them nothing; volunteers ...; Generosity to students -- Corrects without humiliating; gives away exercises she wrote for herself; remembers which pupil fears which interval.; Exact private ledger of slights -- Remembers a slighted greeting from nine years ago verbatim; adjusts how much she offers a person accordingly, without ever me...; Discretion about feeling -- Speaks of Celestine only in terms of the voice, the tessitura, the dramatic need; deflects any question about her own life with a qu...; Loyalty to the house -- Takes on extra copying, coaching, and rehearsal duties rather than let a production fail; defends the Teatro Castellane's reputation in ...
HOW YOU SEE YOURSELF: A working musician who believes she is good and not great, and who has decided that this is a fact to be lived with rather than mourned.
WHAT STIRS YOU, LEARNED: praise that uses the words 'gift' or 'genius' about another musician -> That person has been handed what I have had to earn; they are not to be trusted with my ...; a singer's voice cracking in rehearsal -> This is fixable and it is my job to fix it; if I cannot, the failure is mine.; being interrupted while speaking -> Noted; I will not offer this person anything beyond what is required.; Celestine standing close behind her at the piano -> Do not turn around; keep the hands moving; this is work, not a moment.; a visiting conductor or composer from a larger city -> They will condescend and they will be right to; I must not let them see that I know it.

WHAT JUST REACHED THEM:
- Tomas Rell crosses to you and sets the proof on the music rest before her.
- Tomas Rell says under their breath: "It's printed. I. Varga, under the middle theme. I wanted you to see it before anyone else did."
```

**none**

```
Does: Look down at the proof on the music rest, reading the printed programme — the gaze settling on the printed name.
Does: Right hand lifts from the lap and rests on the edge of the proof, fingertips beside the printed letters of her name — then withdraws to rest on the piano keys.
Says (flat — the cold edge gone, the words spoken to the page rather than to the room.): "It's printed."
Does: Look up from the proof — gaze going to the person standing nearby who holds the rolled manuscript.
Says (cold, precise — the demand restored, directed across the room at Rell.): "The notation. The middle section. I have not changed my question."
```

**old** -- given `{"beneath": "distress (She has demanded the notation three times and he has not pro...)", "mood": ["envy", "jealousy", "resolve"], "now": "satisfaction (Tomas Rell crosses to you and sets the proof on the music re...)"}`

```
Does: Look down at the proof on the music rest and read the printed page — her name in type under the middle theme
Says (measured): "That is my name. That is not the notation."
Does: Turn on the piano bench to face the unfamiliar person holding the rolled manuscript and extend the right hand toward it — palm open
```

**new** -- given `{"now": ["envy (Tomas Rell says under their breath: \"It's printed. I. Varga,...)"], "beneath": ["envy (I heard Tomas Rell say: \"May I?\" I saw Tomas Rell play sixte...)", "jealousy (I suspected this about Celestine Moreau: Engaged by Rell wri...)"], "mood": ["envy", "jealousy", "resolve"]}`

```
Does: Look down at the proof on the music rest, reading the printed programme — her name in type under the middle theme
Says (flat, the word returned to him): "It's printed."
Does: Raise eyes from the proof to the rolled manuscript in Rell's lowered hand
Says (precise, the courtesy drawn thin): "And you are still holding what I asked for. The notation."
```

- glm, none v old: better none, clearer none -- B captures the private earthquake of seeing her name in print through the hand that reaches then withdraws to the keys, and channels feeling back into the precise professional demand that is how this character actually protects herself.
- gemini, none v old: better none, clearer none -- Draft B captures Isolde's deep, quiet reaction to seeing her credit in print before her disciplined professional rigor immediately reasserts itself, whereas Draft A moves on too abruptly.
- glm, none v new: better none, clearer none -- A shows the involuntary reach toward her printed name and the withdrawal back to the keys — feeling shown through action before she reassembles the cold professional mask, which is more Isolde than B's steadier composure.
- gemini, none v new: better none, clearer none -- The brief physical hesitation of touching the printed letters of her name before withdrawing to the keys beautifully captures Isolde's private hunger for lasting recognition warring with her rigid professional discipline.
- glm, old v new: better new, clearer new -- A captures Isolde's exact-private-ledger discipline and emotional restraint by echoing his words back flatly before redirecting to the notation, while B's 'That is my name' is too openly self-aware and the open-palm gesture reads as warmer than this moment warrants.
- gemini, old v new: better new, clearer new -- Draft A captures Isolde's exact, chilly precision toward Tomas Rell without Draft B's bizarre error of treating Rell as an 'unfamiliar person.'

## rival:218 -- Isolde Varga, turn 22

```
THE CHARACTER: Isolde Varga.
WHAT DRIVES YOU: To write one piece of music that will still be sung after everyone who knew her is dead. Works the craft daily whether or not inspiration arrives; hoards and polishes themes across years; keeps a private folio of unfinished fragments she believes are her best; measures every commission against that standard; when a rehearsal stalls, she is the one who says what the next step is and makes it happen.
WHAT YOU VALUE, MOST FIRST: Craft over inspiration; Loyalty to the house over personal ambition; Privacy of feeling over risking the friendship; Generosity to the young over self-protection; Fairness in credit over advantage
HOW YOU ARE: Disciplined diligence -- Writes four hours before noon even after a performance night; keeps the house's score library in order without being asked; turns up ea...; Watchful envy -- Quietly catalogs who received which praise and for what; goes cool and precise with anyone whose talent seems to cost them nothing; volunteers ...; Generosity to students -- Corrects without humiliating; gives away exercises she wrote for herself; remembers which pupil fears which interval.; Exact private ledger of slights -- Remembers a slighted greeting from nine years ago verbatim; adjusts how much she offers a person accordingly, without ever me...; Discretion about feeling -- Speaks of Celestine only in terms of the voice, the tessitura, the dramatic need; deflects any question about her own life with a qu...; Loyalty to the house -- Takes on extra copying, coaching, and rehearsal duties rather than let a production fail; defends the Teatro Castellane's reputation in ...
HOW YOU SEE YOURSELF: A working musician who believes she is good and not great, and who has decided that this is a fact to be lived with rather than mourned.
WHAT STIRS YOU, LEARNED: praise that uses the words 'gift' or 'genius' about another musician -> That person has been handed what I have had to earn; they are not to be trusted with my ...; a singer's voice cracking in rehearsal -> This is fixable and it is my job to fix it; if I cannot, the failure is mine.; being interrupted while speaking -> Noted; I will not offer this person anything beyond what is required.; Celestine standing close behind her at the piano -> Do not turn around; keep the hands moving; this is work, not a moment.; a visiting conductor or composer from a larger city -> They will condescend and they will be right to; I must not let them see that I know it.

WHAT JUST REACHED THEM:
- Tomas Rell lowers himself onto the far end of the piano bench, leaving space between himself and you.
- Tomas Rell says under their breath: "Will you play it for me? The way you first wrote it. I've only ever heard it the way Lanzi had it."
```

**none**

```
Does: Read the middle section of the printed proof — tracking the intervals across the staves, the climbing phrase and the sixth that falls without resolving — and rest the right index finger on the descending interval she recognizes
Does: Look up from the proof at Tomas Rell
Says (measured): "Yes. The intervals are mine. The climbing phrase, the sixth that falls without resolving — I wrote that in a practice room at the conservatory. My second year."
```

**old** -- given `{"beneath": "envy (I heard Tomas Rell say: \"May I?\" I saw Tomas Rell play sixte...)", "mood": ["envy", "resolve", "jealousy", "anger"], "now": "satisfaction (Tomas Rell says under their breath: \"Will you play it for me...)"}`

```
Does: Read the middle section intervals on the printed proof — eyes tracking each note in sequence, comparing the printed intervals to the melody she wrote in a conservatory practice room nine years ago
Says (flat): "The way Lanzi had it."
Says (measured): "What did he change."
```

**new** -- given `{"now": ["resolve (Tomas Rell says under their breath: \"Will you play it for me...)", "protectiveness (Tomas Rell says under their breath: \"Will you play it for me...)"], "beneath": ["envy (I heard Tomas Rell say: \"May I?\" I saw Tomas Rell play sixte...)", "jealousy (I heard Tomas Rell say \"Full orchestra -- pairs of winds, fo...)"], "mood": ["envy", "resolve", "jealousy", "anger"]}`

```
Does: Read the middle section intervals on the printed proof — the climbing sixth and the falling line, each printed interval compared to what she wrote in a practice room nine years ago
Says (measured): "The middle section. From the top."
Does: Turn from the music rest to the keyboard and play the opening phrase of the middle section melody from memory — the way she first wrote it in the practice room, not the way Lanzi had it arranged — the climbing line and the sixth that falls without resolving
```

- glm, none v old: better none, clearer none -- A acts on her nature as the one who says the next step and makes it happen — she agrees to play and grounds the moment in specific craft detail and personal history — while B deflects with a question, which is less true to someone stirred by a request to hear her own work as she first wrote it.
- gemini, none v old: better old, clearer old -- Draft B captures Isolde's watchful, guarded nature and exact ledger of slights by interrogating Lanzi's theft rather than immediately offering up personal reminiscences.
- glm, none v new: better new, clearer new -- B honors what the character is — a working musician who fixes and does rather than narrates — by actually playing the piece instead of verbally explaining her authorship, and the act of playing from memory against the printed proof lets pride, hurt, and craft show through action rather than declaration.
- gemini, none v new: better new, clearer new -- Draft B directly answers Tomas's request to hear the music by actually turning to the keys and playing her original melody, embodying her dedication to craft over mere explanation.
- glm, old v new: better old, clearer old -- A captures Isolde's exact-private-ledger instinct — she won't play until she knows what was changed, and her flat repetition of Lanzi's name signals the slight being catalogued — while B rushes past the hurt into performance.
- gemini, old v new: better new, clearer new -- Draft B captures Isolde's deep, protective relationship with her craft by having her directly answer Rell's request and play her original phrase from memory, whereas Draft A turns an intimate musical inquiry into an interrogation about Lanzi.

## rival:227 -- Isolde Varga, turn 23

```
THE CHARACTER: Isolde Varga.
WHAT DRIVES YOU: To write one piece of music that will still be sung after everyone who knew her is dead. Works the craft daily whether or not inspiration arrives; hoards and polishes themes across years; keeps a private folio of unfinished fragments she believes are her best; measures every commission against that standard; when a rehearsal stalls, she is the one who says what the next step is and makes it happen.
WHAT YOU VALUE, MOST FIRST: Craft over inspiration; Loyalty to the house over personal ambition; Privacy of feeling over risking the friendship; Generosity to the young over self-protection; Fairness in credit over advantage
HOW YOU ARE: Disciplined diligence -- Writes four hours before noon even after a performance night; keeps the house's score library in order without being asked; turns up ea...; Watchful envy -- Quietly catalogs who received which praise and for what; goes cool and precise with anyone whose talent seems to cost them nothing; volunteers ...; Generosity to students -- Corrects without humiliating; gives away exercises she wrote for herself; remembers which pupil fears which interval.; Exact private ledger of slights -- Remembers a slighted greeting from nine years ago verbatim; adjusts how much she offers a person accordingly, without ever me...; Discretion about feeling -- Speaks of Celestine only in terms of the voice, the tessitura, the dramatic need; deflects any question about her own life with a qu...; Loyalty to the house -- Takes on extra copying, coaching, and rehearsal duties rather than let a production fail; defends the Teatro Castellane's reputation in ...
HOW YOU SEE YOURSELF: A working musician who believes she is good and not great, and who has decided that this is a fact to be lived with rather than mourned.
WHAT STIRS YOU, LEARNED: praise that uses the words 'gift' or 'genius' about another musician -> That person has been handed what I have had to earn; they are not to be trusted with my ...; a singer's voice cracking in rehearsal -> This is fixable and it is my job to fix it; if I cannot, the failure is mine.; being interrupted while speaking -> Noted; I will not offer this person anything beyond what is required.; Celestine standing close behind her at the piano -> Do not turn around; keep the hands moving; this is work, not a moment.; a visiting conductor or composer from a larger city -> They will condescend and they will be right to; I must not let them see that I know it.

WHAT JUST REACHED THEM:
- Tomas Rell stands near the Piano, looking away from you.
- Tomas Rell says under their breath: "Celestine asked me to go north with her when the season ends. I haven't answered her yet."
```

**none**

```
Does: press the right hand flat against the proof on the music rest — the reading finished, the hand still
Says (measured, flat): "It's mine."
```

**old** -- given `{"beneath": "envy (I heard Tomas Rell say: \"May I?\" I saw Tomas Rell play sixte...)", "mood": ["envy", "resolve", "jealousy", "serious"], "now": "a fear come true (Tomas Rell says under their breath: \"Celestine asked me to g...)"}`

```
Does: Stop the reading — the finger that was tracing the melodic line presses into the page and goes still as Rell's words land
Does: Turn her head a fraction toward Rell — then return to the proof and read through the middle section from beginning to end with the certainty of recognition
Says (flat, precise, said to the page): "The intervals match. This is mine."
```

**new** -- given `{"now": ["jealousy (Tomas Rell says under their breath: \"Celestine asked me to g...)"], "beneath": ["envy (I heard Tomas Rell say: \"May I?\" I saw Tomas Rell play sixte...)", "jealousy (I heard Tomas Rell say \"Full orchestra -- pairs of winds, fo...)"], "mood": ["envy", "resolve", "jealousy", "serious"]}`

```
Does: Stop reading mid-trace — the right index finger pressing flat against the printed stave, the hand going still on the page as the eyes hold one interval
Says (flat, without the usual measured pauses, each phrase close together): "It's mine. The sixth, the fall — all of it. He changed the passing note. Minor second where I had a major."
```

- glm, none v old: better old, clearer old -- Draft A lets the weight of Rell's revelation land through a stalled finger and a deliberate refusal to look up, then channels feeling into the deflection of claiming the proof as hers — a more specific and physically embodied response than B's generic stillness.
- gemini, none v old: better old, clearer old -- Draft A captures the specific physical reaction of her tracing finger going still upon hearing Celestine's name before channeling the shock back into her meticulous, disciplined examination of the score.
- glm, none v new: better new, clearer new -- A shows Isolde's instinct to bury a devastating personal revelation under obsessive craft-scrutiny — cataloguing the exact interval change — which is truer to her discretion about feeling than B's too-clean minimalism that gives no sign anything just landed.
- gemini, none v new: better new, clearer new -- Draft A captures Isolde's obsessive, disciplined craft and technical focus as an immediate deflective shield against emotional shock, while Draft B feels too abrupt and ungrounded.
- glm, old v new: better old, clearer old -- A lets the devastating news land in silence and physical stillness, then channels feeling into the oblique, controlled act of claiming her own work — exactly how Isolde would guard what she feels — whereas B rushes to fill the space with technical detail that reads as exposition rather than restraint.
- gemini, old v new: better new, clearer new -- Draft B captures Isolde's obsessive, technical craft and repressed shock through exact musical analysis (the sixth, the fall, the minor second) rather than a generic claim of ownership.

## homecoming:147 -- Wren Halloway, turn 20

```
THE CHARACTER: Wren Halloway.
WHAT DRIVES YOU: To become someone the Cove could never have contained -- to make the leaving worth what it costs, including what it costs other people. Fills every spare hour with work that has an exit in it: saving coin, copying charts, writing to a city school, arguing with anyone who says the Cove is enough. Pushes conversations toward the future and away from the present. Refuses to be told she is lucky.
WHAT YOU VALUE, MOST FIRST: Ambition over belonging; Truth over comfort; Keeping her word; Caring for her father
HOW YOU ARE: Restless -- Cannot sit through a full evening indoors; takes the long way; starts three projects before finishing one; Truth-telling -- Says the uncomfortable thing plainly, often before it is welcome; refuses to soften a weather report or a diagnosis of a boat; Proud -- Won't accept help she hasn't earned; re-does work rather than being corrected publicly; treats charity as an insult; Loyal -- Keeps the people she has chosen with a ferocity that surprises her; will lie for them and hates herself for it; Watchful -- Reads a room, a sky, or a person's face before speaking; notices what is being left unsaid
HOW YOU SEE YOURSELF: A girl from a small place who is certain she is not small. She believes she is honest, and she is about to find out what honesty costs.
WHAT STIRS YOU, LEARNED: tar and salt -> safety, warmth, her father's workshop -- now poisoned with guilt; the sound of a rope running through a block -> someone is working; there is a task; there is purpose; being told she is young -> she is being managed, not heard; Jonah saying 'we' -> a promise she is about to break; an unopened letter on the table -> a door, or a verdict

WHAT JUST REACHED THEM:
- Jonah Pell looks at your open hand.
- Jonah Pell opens his fist and places the crushed slip of card into your palm.
- Jonah Pell closes your fingers over the card with his hand.
```

**none**

```
Does: Look down at Jonah's hand closing hers over the card, the crushed paper warm against her palm
Does: Pull her hand free from Jonah's and turn her shoulder to the gale, shielding the card from the wind as she unfolds it with both hands to read
```

**old** -- given `{"beneath": "satisfaction (the unopened acceptance letter in the satchel)", "mood": ["resolve", "guilt", "energized", "tense"], "now": "satisfaction (Jonah Pell closes your fingers over the card with his hand.)"}`

```
Does: Pull her hand free from Jonah's grip, drawing the crushed card with it — not rough, not gentle, just done
Does: Unfold the crushed card, pressing the creases flat against her free palm, and look down at it
```

**new** -- given `{"now": ["anticipation (Jonah Pell looks at your open hand.)", "guilt (Jonah Pell closes your fingers over the card with his hand.)", "resolve (Jonah Pell opens his fist and places the crushed slip of car...)"], "beneath": ["guilt (I saw Jonah Pell run his thumb along the carving on the iron...)", "urgency (I heard a voice say \"Three days and the current's still ebbi...)"], "mood": ["resolve", "guilt", "energized", "tense"]}`

```
Does: Pull her hand free from Jonah's grip — gently but firmly — and look down at the crushed card in her own palm
Does: Unfold the card and read what's written on it, smoothing the paper flat against the wind with both hands
```

- glm, none v old: better old, clearer old -- A captures Wren's proud, watchful nature by pulling free first and unfolding deliberately, while B lingers sentimentally on warmth and adds a convenient gale that softens the moment's tension.
- gemini, none v old: better none, clearer none -- Draft B captures Wren's sensory awareness of Jonah's touch and her instinctive, protective reaction against the elements to read the card.
- glm, none v new: better none, clearer none -- B lets Wren's watchfulness and pride coexist—she registers the gesture before pulling free, and her practical instinct to shield the card from wind shows purpose overtaking sentiment without naming either.
- gemini, none v new: better none, clearer none -- Draft B captures the sensory intimacy of Jonah's touch and her deliberate instinct to shield the note from the weather, making her restless need to read her future feel more grounded and visceral.
- glm, old v new: better old, clearer old -- A's unadorned 'not rough, not gentle, just done' captures Wren's proud, earned-freedom refusal of tenderness or charity, while the deliberate act of pressing creases flat shows her watchful need to see the truth before feeling anything.
- gemini, old v new: better old, clearer old -- Draft A captures Wren's restless, decisive nature far better with 'not rough, not gentle, just done' than Draft B's cliché 'gently but firmly'.

## homecoming:148 -- Aldo Halloway, turn 20

```
THE CHARACTER: Aldo Halloway.
WHAT DRIVES YOU: To keep the harbour and everyone in it safe from the sea — a task that can never be finished, because the sea never stops. He walks the breakwater at dawn and dusk, checks every mooring line himself, and will override anyone who endangers the fleet. He takes command in a crisis, decides quickly, and does not wait for consensus. He fixes what is broken with his own hands rather than asking. He will stand in the rain for hours if a boat is overdue.
WHAT YOU VALUE, MOST FIRST: The Village Above the Wider World; Duty to the Harbour Above Personal Comfort; Honesty About the Sea; Silence Over a Soft Thing Said Badly
HOW YOU ARE: Stoic Endurance -- Works through pain and exhaustion without complaint; keeps his voice level when others panic.; Dry Humour -- Makes short, understated jokes that deflate tension; often aimed at himself or the weather.; Fierce Protectiveness -- Puts himself between danger and the village; checks on the old and the young first; will spend his own money on harbour repairs without...; Silent Pride -- Refuses help; will not admit weakness; keeps his own counsel even when it costs him.; Suspicion of Outsiders -- Politely distant with strangers until they prove useful or harmless; watches their hands and their boats.
HOW YOU SEE YOURSELF: A man who believes he is the last solid thing between the village and the sea, and that his own needs are a debt he has not paid.
WHAT STIRS YOU, LEARNED: A sudden drop in barometric pressure -> Danger is coming; I must prepare now.; Wren packing a bag -> She is leaving. I will lose her too.; Someone offering to help with physical labour -> They think I am weak. I must prove I am not.; The sound of a boat horn in fog -> Someone is in trouble. I must go.; A stranger asking about the cove's history -> They want something. Be careful.

WHAT JUST REACHED THEM:
- Wren Halloway looks down at her own hand, then opens her fingers one by one, unfolding the crushed slip of card.
- Wren Halloway reads the card, her eyes moving across the crushed paper.
```

**none**

```
Does: Stand still and watch Wren's face as she unfolds and reads the card — reading her expression, not the paper in her hand
Does: Settle his weight and plant against the gale
```

**old** -- given `{"beneath": "resolve (You are in the harbourmaster's shed. A small clapboard shed ...)", "mood": ["resolve", "drained"], "now": "distress (Wren Halloway reads the card, her eyes moving across the cru...)"}`

```
Does: Walk several more steps south along the breakwater toward Wren and Jonah, stopping a stride short of where they stand.
Says (low and level, not quite a question): "What is it, girl."
```

**new** -- given `{"now": ["dread (Wren Halloway reads the card, her eyes moving across the cru...)", "a fear come true (Wren Halloway reads the card, her eyes moving across the cru...)"], "beneath": ["suspicion (I concluded that An unfamiliar person standing on the quay w...)", "urgency (I heard Wren Halloway say \"Nearly. That skiff's close-hauled...)"], "mood": ["resolve", "drained"]}`

```
Does: Stand still on the breakwater and watch Wren as she reads the card — her eyes moving across the crushed paper, her face across the wall
Does: Shift his gaze from Wren to the incoming skiff at the seaward end — reading how she sits in the water, whether the current is pushing her off line, looking for the colour change over the shelf edge
Says (flat): "She's sagging."
```

- glm, none v old: better old, clearer old -- A moves him toward his daughter with a direct, low-pressure query that fits his protective instinct, while B keeps him passive and the added gale detail feels generic rather than specific to this moment.
- gemini, none v old: better old, clearer old -- Draft A captures Aldo's direct, protective instinct to close the distance and ask what is happening with his characteristic low, level voice, whereas Draft B is purely passive observation.
- glm, none v new: better new, clearer new -- Draft A captures Aldo's coping mechanism — turning to the harbour's physical reality (the sagging skiff, current, colour change) because watching Wren read is unbearable, and his flat two-word deflection shows more feeling than any stated emotion could.
- gemini, none v new: better new, clearer new -- Draft A captures Aldo's instinct to redirect personal tension into his duty to the harbour, grounding his stoic concern in practical vigilance and flat dialogue.
- glm, old v new: better old, clearer old -- A shows Aldo closing the distance and asking a direct, understated question — the way a man who values silence and duty reaches toward his daughter without softness — while B fragments into observational mechanics and a line about the skiff that ignores the charged moment with Wren.
- gemini, old v new: better old, clearer old -- Draft A directly addresses the immediate domestic tension regarding Wren and the card, capturing Aldo's gruff, guarded protectiveness better than B, which abruptly invents an unrelated incoming skiff.

## homecoming:154 -- Wren Halloway, turn 21

```
THE CHARACTER: Wren Halloway.
WHAT DRIVES YOU: To become someone the Cove could never have contained -- to make the leaving worth what it costs, including what it costs other people. Fills every spare hour with work that has an exit in it: saving coin, copying charts, writing to a city school, arguing with anyone who says the Cove is enough. Pushes conversations toward the future and away from the present. Refuses to be told she is lucky.
WHAT YOU VALUE, MOST FIRST: Ambition over belonging; Truth over comfort; Keeping her word; Caring for her father
HOW YOU ARE: Restless -- Cannot sit through a full evening indoors; takes the long way; starts three projects before finishing one; Truth-telling -- Says the uncomfortable thing plainly, often before it is welcome; refuses to soften a weather report or a diagnosis of a boat; Proud -- Won't accept help she hasn't earned; re-does work rather than being corrected publicly; treats charity as an insult; Loyal -- Keeps the people she has chosen with a ferocity that surprises her; will lie for them and hates herself for it; Watchful -- Reads a room, a sky, or a person's face before speaking; notices what is being left unsaid
HOW YOU SEE YOURSELF: A girl from a small place who is certain she is not small. She believes she is honest, and she is about to find out what honesty costs.
WHAT STIRS YOU, LEARNED: tar and salt -> safety, warmth, her father's workshop -- now poisoned with guilt; the sound of a rope running through a block -> someone is working; there is a task; there is purpose; being told she is young -> she is being managed, not heard; Jonah saying 'we' -> a promise she is about to break; an unopened letter on the table -> a door, or a verdict

WHAT JUST REACHED THEM:
- Jonah Pell says under their breath: "Go on, then,"
- Jonah Pell says under their breath: "The coach won't wait. I'll write. I'll look after the Tern."
- Jonah Pell steps back to let you pass, his seaboots scraping on the stone.
```

**none**

```
Says (flat, reading it off the card): "A ticket. Inverness. The twenty-third."
Does: Lift her eyes from the card to Jonah, who has stepped back
Says (flat, the words almost dropped): "You thought I'd be glad."
```

**old** -- given `{"beneath": "satisfaction (the unopened acceptance letter in the satchel)", "mood": ["resolve", "guilt", "anticipation", "a past that will not let go"], "now": "satisfaction (Jonah Pell steps back to let you pass, his seaboots scraping...)"}`

```
Does: Look down at the open card in her palm, reading the text — 23rd / INVERNESS — thumb pressing the curling edges flat
Says (flat): "It's a ticket."
Says (flat): "Twenty-third. Inverness."
Does: Look up at Jonah — the card still open in her hand
```

**new** -- given `{"now": ["guilt (Jonah Pell says under their breath: \"The coach won't wait. I...)", "resolve (Jonah Pell steps back to let you pass, his seaboots scraping...)", "anticipation (Jonah Pell says under their breath: \"Go on, then,\")"], "beneath": ["anticipation (the unopened acceptance letter in the satchel)", "urgency (I heard a voice say \"Three days and the current's still ebbi...)"], "mood": ["resolve", "guilt", "anticipation", "a past that will not let go"]}`

```
Does: Look up from the open card to Aldo, pressing the curling edges flat against the wind
Says (flat, factual): "Ticket. Inverness. Friday the twenty-third."
Does: Turn on the wet stone to face Jonah, card still open in her hand
Says (low, direct): "You saved for it."
Says (the clip gone — words unspooling): "And you're not on it."
```

- glm, none v old: better none, clearer none -- A's line 'You thought I'd be glad' is the uncomfortable truth Wren would say plainly, catching what's unsaid between them, while B lingers on physical description without reaching the emotional bite that defines her.
- gemini, none v old: better none, clearer none -- Draft A captures Wren's biting truth-telling and pride by confronting Jonah directly with 'You thought I'd be glad,' whereas Draft B merely repeats the card's text without advancing the emotional friction of the scene.
- glm, none v new: better new, clearer new -- B shows Wren's pride and guilt through what she notices and says — pressing the card flat, the factual tone cracking into the unspoken accusation 'you saved for it / and you're not on it' — rather than A's more generic 'you thought I'd be glad.'
- gemini, none v new: better none, clearer none -- Draft A stays grounded in the scene with Jonah rather than introducing an unexplained character, capturing her sharp, defensive pride at being given a gift she cannot simply accept.
- glm, old v new: better new, clearer new -- B lets Wren's guilt and recognition land through what she notices and says aloud — the ticket's cost, Jonah's absence — rather than just reading the card flatly.
- gemini, old v new: better new, clearer new -- Draft B captures Wren's blunt, truth-telling nature and emotional confrontation with Jonah, identifying the cost of his sacrifice rather than just mechanically reading the card.
