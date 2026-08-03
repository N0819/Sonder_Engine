# Features

What Sonder Engine does, in plain language. One line per feature, describing
what you get rather than how it is built.

This is a catalogue, not an argument. [`Design.md`](../Design.md) explains why
the system is shaped the way it is and carries the verified built / partial /
not-built table; [`docs/UNBUILT.md`](UNBUILT.md) is the register of what is
missing or broken; [`README.md`](../README.md) covers installing and running.
Where a line here says **(partial)**, the feature exists and works but is
narrower than it sounds — those two documents have the detail.

---

## Playing

- **Stories** — Each story is its own saved session with a name, an opening
  scenario, the persona you play, and a cast you can add to, retire from or
  bring back at any time.
- **Write anything** — Type an action, a line of speech, both, or nothing at
  all and let the scene establish itself.
- **Approaching is not arriving** — Walking towards somewhere leaves you closer
  to it, not inside it. Reaching a building and going through its door are
  separate beats, and the engine will not decide you have done either until you
  say so.
- **Attempts versus statements** — "I try to take the key" starts something
  others can interfere with; "I take the key" is treated as true and the world
  works out what follows.
- **Your words are kept** — What you wrote is never silently replaced, and the
  narration never repeats your own lines back at you or puts words in your
  mouth.
- **Writing for someone else is an offer** — If you write what a character
  thinks or how they answer, it is handed to that character to accept, refuse
  or reinterpret rather than enacted for them.
- **Point of view follows how you write** — First, second or third person is
  detected from your own phrasing, held between turns, and only changed on a
  decisive shift, so one stray "you" cannot flip a whole campaign's voice.
- **Style exemplars** — Supply passages that calibrate the prose voice without
  supplying any content.
- **Genre & style guide** — A standing instruction for everything the engine
  invents: genre, tone, notes for events and for new rooms, a never-generate
  list, and how far the weather may go.
- **Multiplayer** — Attach extra player personas so more than one person can
  act in the same scene, each with their own position, perception and prose.
- **Guest invites** — A single-use join code, expiring in 30 minutes, that lets
  a friend play one persona in one story and reach nothing else.

## A turn, and what you can do to it

- **A turn is a chain of specialists** — Understand your input, look up world
  facts, decide what each person could notice, let them react, resolve what
  actually happened, filter it again, write the prose, save. Not one model
  doing everything at once.
- **Watch it happen** — Each stage reports in plain English as it runs, with a
  timer, and you can stop a turn mid-flight.
- **Inspect any stage** — Every stage's exact output is saved and browsable,
  including the model's private reasoning where the provider exposes it.
- **Reroll** — Throw away the newest beat and generate it again from the same
  input.
- **Re-run from a stage** — Recompute a turn from any point onward, keeping the
  earlier work.
- **Edit a stage by hand** — Open a stage's output, change it, and save it back
  as what the story runs on.
- **Variant history** — Every attempt is kept as a switchable alternative.
- **Edit what you wrote** — Rewrite your own input and recompute from it.
- **Edit the prose** — Fix the narration of a past beat without disturbing what
  mechanically happened.
- **Delete the last turn** — Remove the newest beat and roll the whole world
  back to before it.
- **Branch here** — Fork any past turn into a complete independent story.
- **Resume an interrupted turn** — A turn cut off by a dropped connection or a
  closed tab restarts at the first stage that never finished.
- **All or nothing** — A turn either saves completely or leaves no trace.
- **A warning before a rewind** — Anything that recomputes a turn tells you
  first that world state, memories and lore will roll back with it.

## What each mind is allowed to know

The engine's founding rule: no character receives information it did not
legitimately perceive, learn, remember or infer.

- **No shared transcript** — Each character gets its own private description of
  what it personally registered. There is no omniscient record any mind can
  read.
- **Barriers decide what crosses** — A window passes sight but not sound, bars
  pass both, a curtain passes bodies; each boundary answers separately for
  sight, sound and smell.
- **Smell is its own channel** — Scent carries through openings and is muffled
  by a closed door, so cooking or smoke reaches you from a room you cannot see
  into.
- **Muffled hearing** — Speech at the edge of earshot arrives as a fragment,
  not a full line, and a whisper does not cross a hall.
- **Felt but not seen** — Someone you can touch but not see registers as motion
  and pressure; you never learn what act is producing it.
- **Concealed acts are cut sentence by sentence** — A hidden action is removed
  from the version each person who should not see it receives, while the overt
  parts of the same beat survive.
- **Strangers stay strangers** — Someone you have not been introduced to is
  referred to by appearance, never by name — in what you see, in dialogue
  records, and in their own memory of you.
- **Disguises** — A concealed appearance is what everyone actually sees; only
  those who legitimately know the truth know it.
- **Body language you can catch** — Characters produce a surface manner and
  small physical tells, and which reach you depends on your eyesight, how well
  you know them, and whether you were paying attention.
- **Blind spots** — What is behind you, what is in an unlit corner and what is
  sealed in a container are all handled as things you do not see.
- **Graded impressions** — Everything perceived is tagged with how intense,
  sudden and ambiguous it was, so a bang and a murmur are appraised differently.

## Characters

- **They decide, the world adjudicates** — A character declares what it
  attempts; whether it works is never its own call.
- **Appraisal before action** — What the beat means for their goals, how novel
  it is, how much control they have, whether they can cope, whether it fits
  their values, what it does to their body — then they act.
- **Options weighed** — Several possible responses are considered with their
  risks before one is taken, and the discarded ones stay visible in the record.
- **Own body only** — A character feels their own pain, exhaustion and comfort
  and has no access to anyone else's interior.
- **They can say nothing** — Silence is a legitimate answer.
- **They do not repeat themselves** — Recent lines are fed back, repeated
  sentence shapes are detected, and a line reissued word-for-word forces a
  rewrite.
- **Per-character variance** — Each has its own creativity and cognitive tier,
  so a lead behaves more consistently than a passer-by.
- **Their own map** — Characters build a private map of ground they have walked
  or seen into, correct a remembered doorway when they find it gone, and forget
  the oldest places when it grows too large.
- **They know where they are going** — A goal naming a place they know becomes
  a live journey with progress, and running down a corridor tells them whether
  it takes them nearer or further.
- **Places remembered for what they are for** — Hunger or exhaustion surfaces a
  place they know answers that need, and roughly how far it is.

## Memory

- **Six kinds of knowing** — Every memory records how it was acquired:
  witnessed, heard, told, read, inferred or remembered.
- **You remember what you registered** — Memories are minted from each
  character's own filtered view, so two people in a room remember different
  things and one of them can be wrong.
- **Recall is cued** — What surfaces is chosen by meaning, exact phrases,
  keywords, importance, recency, and where the character is standing.
- **No spoilers from the future** — A character deciding this turn can never
  retrieve a memory of how this turn turned out, even after a reroll.
- **Unbidden recall** — A character who is measurably stuck gets one important,
  deliberately unlike-the-moment memory surfaced on its own.
- **Neighbouring memories come along** — Recalling one episode can pull the beat
  either side of it.
- **Abandoned beliefs stop dominating** — An inference the character has talked
  themselves out of stops outranking what replaced it, without being erased.
- **Consolidation** — Older memories fold into a running autobiography and the
  raw ones are archived, so a long story stays affordable.
- **Three separate autobiographies** — What they experienced, what they were
  told and what they worked out are summarised separately, so a guess cannot
  quietly become something they know.
- **Forgetting has rules** — Only low-importance, already-summarised material is
  archived. A grudge or a promise is never aged out.
- **Memory browser** — Search, filter, read, edit, add, archive, import and
  export any character's memories, see why each was recalled, and preview the
  exact memory context a character is given.

## Psychology

- **Two kinds of stress** — Distress (threat, low control, pain) and
  non-distressing arousal are tracked separately, so a character at the ceiling
  of an intense pleasant experience is not reported as composed.
- **Chronic load** — A slow accumulating burden with its own recovery rate, and
  a point at which a character is overloaded.
- **Pain and pleasure are independent** — A comforting touch can hurt a bruise
  and still be welcome.
- **Unresolved charge** — A drive building over many beats keeps building, and
  discharges only when the character declares it resolved.
- **Ambient comfort** — What a body rests against contributes ease on its own,
  worth more when exhausted, and habituating if they stay there.
- **Mood decays, stances do not** — Mood relaxes toward a personal baseline over
  story time; trust and grudges move only when something moves them.
- **Wants, intentions, projects, drives** — Beat-level wants under longer
  intentions, under at most two standing projects, under the one thing a
  character fundamentally lives for.
- **Projects with real commitment** — A project is adopted against a concrete
  "done when", serves a probation, and surfaces as drift when abandoned rather
  than silently decaying.
- **Drive rupture** — A shattering event can crack what a character lives for,
  opening a window in which they may genuinely change, and recording the old
  drive as a scar with the reason it ended.
- **Composure fails visibly** — A character under sustained assault on what they
  live for can no longer play untouched calm.
- **Tells that get paid off** — A physical cue is stored with the private reason
  it betrayed, so a later beat can surface that reason instead of leaving the
  gesture as empty significance.
- **Learned beliefs and associations** — Both strengthen with evidence and
  weaken without it; some beliefs are protected from casual revision.
- **Sensation crowds out thought** — Intense feeling narrows what a character
  can theorise, how many open questions they hold and how far ahead they plan,
  while leaving plain observation sharp.

## Beliefs about other people

- **Private theories** — Each character keeps its own hypotheses about what
  others feel, want, know and are like, with confidence that decays at
  different rates for different kinds of claim.
- **Guesses stay labelled** — A conjecture is held as "I suspect", so a
  character cannot read their own theory back as fact.
- **Open questions** — Each mind carries one to five things it is actively
  wondering about, steady between turns, shrinking when overwhelmed.
- **Second thoughts** — A belief formed in extremis is re-opened once the
  character is calm rather than standing forever.
- **Relationships** — Trust, familiarity, warmth and fear per person, moved by
  events and never by a clock. *(partial: stance changes carry a triggering
  note, but there is no full history answering "why does she distrust him?")*
- **Recognition ledger** — Who knows whose name, changing only when an
  introduction actually happens on the page.
- **Dramatic irony panel** — A live list of what every character believes
  without having witnessed it, so you can watch misunderstandings form.
- **Promise panel** — Every promise anyone has made, in order.

## Conversation and background life

- **Reaction phase** — When your action can be interfered with, everyone present
  declares their reaction blind to the others.
- **Autonomous exchanges** — Characters can hold a short back-and-forth within
  one turn, each speaker hearing only what was legitimately audible.
- **Stop conditions you control** — End the exchange when someone addresses you,
  asks you a question, or falls silent; NPC-to-NPC talk and NPC initiative can
  be switched off separately.
- **Autonomy dial** — One 0–100 setting scaling how much a beat may spend.
- **Speech budget** — Style, minimum and maximum line counts and a variance
  setting control how much characters tend to say.
- **Extras who persist** — Named people with no character sheet are tracked
  automatically, with what they said and where they usually stand.
- **Extras are never furniture** — An extra who is addressed or owed a reply is
  forced a line or a small action rather than standing motionless for twenty
  turns.
- **Scene life** — Optionally one call voices every extra in the room at once,
  in two flavours: one that only sees what everyone present heard, and a richer
  one that includes lines aimed at a single listener.
- **Their inventions are claims** — A detail an extra invents is recorded as
  hearsay for the Director to confirm, contradict or let expire.
- **Promotion into a real character** — An extra can become a full character
  with a sheet, psychology and memory — on request, or automatically after a
  number of turns of deliberate interaction that you set. Automatic promotion
  is off unless you switch it on, and extras chattering to each other never
  count toward it.

## The world

- **Rooms and doorways** — A graph of named rooms joined by boundaries: open
  arch, door, closed door, window, bars, curtain or solid wall.
- **Rooms appear as you reach them** — And a place named twice under two
  spellings is collapsed into one rather than becoming two.
- **Lasting room identity** — Every room keeps a stable identity for the whole
  story, including across eras.
- **Places within a room** — A room names its own features (the hearth, the bar,
  a corner table) and people stand at or beside them, which is what makes
  "within reach" and "across the room" true rather than decorative.
- **Compass bearings** — Doorways carry real directions, and two sides of the
  same doorway are not allowed to disagree.
- **Ahead, behind, left and right** — Worked out from how you entered and which
  way you face, so "the door behind you" is the one you came through.
- **Looking down a passage** — You can see into adjoining rooms through an open
  or glazed boundary, and along a straight corridor until it bends.
- **Running** — Cross several rooms in one beat, following a corridor round its
  bends until a junction, a door, darkness or a dead end stops you; the rooms
  crossed are remembered.
- **Following by choice** — Players and characters can deliberately follow a
  particular person across ordinary travel. The relation persists until the
  follower chooses incompatible conduct or stops, and characters know whom
  they are following. It grants no extra speed or access: a sprint can leave a
  follower behind, a closed barrier still blocks them, and catching up requires
  a real later movement decision.
- **Stepping through a doorway** — A body part-way through stays visible to the
  room it is leaving for a beat rather than vanishing.
- **Up and down** — Stairs and ladders read as above and below, not as another
  side door.
- **Destroying a place** — A building, vehicle or region can be destroyed; its
  rooms are retired rather than deleted, stay readable as history, and anyone
  inside is moved out.
- **Split parties** — Two groups who walk apart run separately, neither
  learning what the other did until they reunite.
- **Move someone by hand** — Relocate a character from the cast panel while the
  story is idle, without generating a beat.

## Objects, bodies and clothing

- **Objects** — Things with their own description, state, aliases and
  portability, created as the story needs them.
- **Containers you can be inside** — A jar, cage, crate or tent has an interior;
  whether you can be seen depends on whether it is opaque, glass, barred or a
  soft flap, and a shut lid conceals what glass would show.
- **Being carried** — You can be in someone's hand, pocket or pack, and go where
  they go; getting out is an explicit act.
- **Vehicles** — Interior rooms, a hatch that opens or seals, and journeys with
  an arrival time; under way its doors lead nowhere, and on arrival the doorway
  opens onto wherever it docked — including a car on a ferry.
- **Portals** — Two rooms joined by a link that opens and closes, with the
  doorway appearing and disappearing with it.
- **Bodiless voices** — A ship's computer or building PA can be present and
  audible everywhere without standing in any room.
- **Size and scale** — A body can be shrunk or grown, changing what it can lift,
  reach or step over, breaking holds that no longer make sense, and persisting
  until something changes it back.
- **Contact** — Who is touching whom, with a manner and body parts, ending by
  itself when they are no longer in the same place. A hand described a second
  time in a new place has MOVED, not multiplied — so a story does not
  accumulate a woman with four hands on someone. Two hands doing two things are
  said in one breath, or named apart ("her left hand"), and then both stand.
- **Contact detail** — A hold can carry how it feels: feather-light, firm,
  beneath the shirt, cold. It travels with the touch and changes as the touch
  changes.
- **Where in a room you are** — At the bar, at the hearth, on the bed, beside
  someone. This decides whether a whisper reaches you whole, whether someone is
  within arm's reach or across a hall, which side of you they are on, and
  whether a body can be somewhere you are not looking. Rooms name their own
  fixtures, and the engine works out where people are from what they are
  touching — so putting a hand on the quilt is enough to be at the bed, and you
  stay there after you let go.
- **Beds and other surfaces** — Being on one is a real place to be, not a
  sentence: it survives the beat that put you there, contributes warmth and
  softness to how your body feels, and someone lying on it while you sit on its
  edge are both true at once.
- **Restraint** — Held, bound, pinned or encased carries through the world as a
  real limit rather than a line of prose.
- **Clothing** — Authored starting clothes seed a story once and stay separate
  from the permanent body description; everything worn, removed or disarranged
  afterwards is live story state.
- **Clothes go on body parts** — Head, torso, arms, hands, waist, groin, legs
  and feet, outermost garment first, so a character can be half-undressed as an
  actual state rather than as a sentence somebody has to remember. This is where
  clothing is written on a card; an older or imported card has its clothes
  sorted onto body parts automatically, ready to be corrected.
- **Worn at, versus worn over** — A ribbon, a necklace, a ring or a pair of
  spectacles sits somewhere without covering it, so someone in nothing but a
  hair ribbon is bare-headed, and taking it off uncovers nobody.
- **Layers** — Garments in one place are ordered outermost first, so an
  under-kimono keeps covering when the kimono comes off, and what is hidden
  underneath is not described as though it were on show.
- **One garment, several body parts** — A kimono, a toga, a dress or a coat is
  one thing covering many places, and comes undone as one thing. A card says
  what each garment covers with a dropdown of tick-boxes, or leaves it on
  "auto" and it is worked out from the name. The waist is the belt line only —
  a sash does not cover what a pair of trousers does, which is the distinction
  that stops someone in nothing but a belt reading as dressed.
- **Undressing takes time** — A garment goes worn, then loosened, then open,
  then off, one step per beat. Saying so plainly — ripping it off, tearing,
  stripping, in one motion — does it at once, whether it is the player or a
  character who says it, and only to the person it was actually said about.
  Getting dressed is not slowed down.
- **Clothes take damage of their own** — A spill, a tear, soaking or scorching
  belongs to the garment, not to the person wearing it: it stays until
  something changes it, and goes with the garment when it comes off, so a
  stained shirt is a stained shirt on the floor. A blow that lands on a covered
  part of someone marks both the clothes and the body — but the coat stays cut
  until it is mended, while the wound heals.
- **Clothes that come off are still there** — A removed garment becomes a real
  object in the room, so it can be picked up, carried, handed over, or put away
  in a wardrobe.
- **A garment is one garment, however it is described** — "the robe", "her
  sheer black robe" and the full name it was written down under all mean the
  same robe. A story cannot end up dressing someone in two copies of the same
  thing, one of them half off, because a sentence used a shorter name; and a
  wardrobe that already went wrong repairs itself the next time it is read.
- **A change of clothes is never quietly lost** — If a beat says something about
  what someone is wearing, it lands: on that garment if she is wearing it, on
  the outfit as a whole if it is about all of it, and as a new garment if the
  story has dressed her in something the wardrobe had not heard of yet.
- **What is underneath** — A card can describe what each region shows once
  nothing covers it. Off by default and switched on in Settings; with it off, a
  bare region is still reported as bare and the body's own description stands in.
- **Fill body and clothing** — A button on any character or persona card writes
  the body and the starting outfit from what is already on the card plus a line
  of your own, with the underneath descriptions as a separate tick-box. It shows
  you a proposal; saving is still yours.
- **Visible damage** — Rooms and bodies carry overlays like smoke, wreckage,
  scorching or blood that persist and feed both the room's picture and its
  sound.

## Weather, light and the body

- **A storm is not always an electrical storm** — Lightning and thunder need a
  storm sky that is not full of snow or sleet. A blizzard is a storm and it does
  not flash; hail, which comes out of the same convective weather as lightning,
  still does.
- **Thundersnow** — Rarely, a blizzard turns electrical, and then it flashes and
  cracks like any storm. It happens about one snowing storm in nine, decided the
  same seeded way as the rest of the weather, so a reroll cannot summon it and a
  replay cannot lose it.
- **One sky** — A scene has a single sky — clear, fair, overcast, fog or storm —
  with rain, drizzle, snow, sleet or hail at a strength, plus wind and
  temperature.
- **Weather only where it belongs** — A story acquires weather when its fiction
  establishes one, so a starship or a sealed interior never gets any.
- **Rooms get different shares** — Each room is open, sheltered or enclosed,
  which decides whether the sky is visible, whether rain lands on you, and
  whether wind reaches you.
- **Hearing a storm you cannot see** — A cellar hears a downpour it cannot see,
  fading from present to muffled to faint as you go deeper, with thunder
  carrying furthest.
- **The sky moves on its own** — Weather drifts about once an hour of story
  time, and a reroll cannot produce a different sky.
- **What weather leaves behind** — Rain leaves damp ground, then puddles, then
  churned mud; snow piles into drifts; a freeze turns wet ground to ice. It
  stays after the sky clears and dries more slowly than it arrived.
- **Weather severity** — Set how far a story's weather may go: calm (scenery
  only, nothing accumulates), seasonal, harsh, or catastrophic.
- **Light** — A room can be dark, dim, lit or bright, and going dark is a real
  change to the place.
- **Carried and built lights** — Any object can be a light source: a hearth
  fills a room, a torch makes a pool around whoever carries it, and dousing it
  leaves the object intact and the room dark.
- **Shapes in the gloom** — Dim light shows movement and outline but not faces;
  dark stops sight entirely; light through an open doorway lifts a dark room
  only as far as shapes.
- **Bodily condition, off by default** — Breath, stamina, nourishment and injury
  are a per-story switch; off means genuinely absent, not zeroed.
- **They move with time, not turns** — And speak up only when they cross into
  something worth feeling: tired, very hungry, badly hurt.
- **Suffocation** — Sealing someone into a closed container starts an air
  countdown of about fifteen minutes; being visible through glass does not help.
- **Rest** — Lying on a bed, bedroll or furs recovers stamina without anyone
  declaring that they are resting. *(partial: sleep is meant to restore far
  faster, but the sleeping state does not yet feed that calculation.)*
- **Going under and waking** — Dazed, asleep, sedated or unconscious; a gated
  mind takes no turn, and waking is the world's decision. If you are
  unconscious the narration gives you a dim interior beat rather than inventing
  surroundings.
- **Condition tracker** — Your own vitals sit beside the composer, with the rest
  of the cast's available in the Cast panel or optionally on screen.

## Time and timelines

- **A story clock** — In-story time in seconds with a readable label, so a beat
  covering three seconds and one covering three hours cost the world
  differently.
- **Assert time** — Declare that hours pass and the world advances.
- **Things that arrive later** — Journeys, expiries and delayed consequences
  fire on the turn they are due, identically on a reroll.
- **News travels** — Word of a distant event reaches an audience after a delay
  derived from distance, arriving as something heard rather than witnessed.
- **Player-scheduled events** — A future event you narrate is queued for the
  next beat rather than dropped, and re-queued if that beat ignores it.
- **Frames (other eras)** — Play a flashback, a flash-forward or a visit to the
  past as its own thread of turns, with travellers keeping their memories while
  natives know only their own time.
- **Per-era cast state** — A character can be alive in one era and dead in
  another, with separate mood and status.
- **Fixed points and paradox** — Mark facts about the past as load-bearing;
  changing them later triggers an escalating paradox instead of silently
  rewriting the story.
- **Choosable paradox consequences** — From pure atmosphere through an
  environmental hazard, decaying memory confidence, or a hunting enforcer.

## Lore

- **Nested lorebooks** — A tree of books; a child can inherit from its parent,
  be reference-only, or be sealed off.
- **Linked books** — Books link to each other and retrieval follows those links
  a couple of hops, weighting distant books below the ones you attached.
- **Scoped lore** — Books scoped to a world or a location so the right material
  surfaces in the right place.
- **Canon written during play** — Facts established in the story are written
  back into the story's own book.
- **Canon lock** — Lock an entry so nothing may rewrite it; entries settle into
  locked canon on their own once they are old enough. *(partial)*
- **Books that follow a thing** — A book pinned to a ship or building reports
  what is aboard or nested inside it right now.
- **Lorebook generation** — Have a whole tree drafted for a setting as a
  resumable job you review before applying.
- **Contradiction tracking** — Entries can record that they contradict another,
  so conflicting canon is tracked rather than silently stacked.

## Prose

- **The narrator knows only what you saw** — It renders your perception and your
  own declaration, with no access to the objective record, the dice, or anyone
  else's mind.
- **Other people's lines are verbatim** — Dialogue that reached you is
  reproduced exactly, once; description is cut before a spoken line is.
- **Automatic rewrite on real errors** — A draft that drops or alters a line,
  flips someone's pronouns, names you in third person, renders a reply before
  the line it answers, misattributes a quote, puts a character in the wrong
  room or shows a shut door as open is sent back for correction.
- **Craft screen** — Stock AI phrasing triggers up to two rewrites, kept only if
  the new draft is genuinely cleaner and loses no dialogue.
- **Anti-repetition** — Word-runs already used, over-used set dressing and
  duplicated sentences are detected and suppressed, so the room stops narrating
  its own clock every turn.
- **Pacing** — One to three paragraphs sized to how many distinct beats the turn
  contains.
- **Spatial restraint** — Directions and exits are mentioned when they changed or
  the beat turns on them — unless you deliberately look around, which gets a
  full survey.
- **Private voice setting** — A per-persona style instruction only the narrator
  sees.

## The reading view

- **The transcript** — A single scrolling column of serif prose at a proper
  measure, with what you typed shown beside the narration it caused.
- **Four text sizes** — Scaling the fiction only, leaving the interface alone.
- **Scene mood wash** — The background drifts slowly between calm, tense, warm,
  somber and triumphant tints to match the beat you are looking at.
- **Faded superseded beats** — Turns a later edit made out of date are dimmed in
  place rather than hidden.
- **Timeline switcher** — Move between eras when a story has more than one.
- **Five themes** — Sonder, Tavern, LCARS, Stone and Ink, each previewed before
  you pick it, stored per-device and never touching your stories or exports.
- **Toasts and an activity panel** — Nothing fails silently, and long jobs run in
  a corner panel with a live count while you carry on reading.
- **Reduced motion respected** — Weather and its flashes are skipped entirely
  rather than merely hidden.
- **Phones and tablets** — Swipe-in sidebar, scrolling toolbar, turn controls
  reachable without a mouse.
- **Keyboard** — Ctrl+Enter sends, Escape closes dialogs one layer at a time,
  sidebar rows are focusable.

## Pictures and sound

- **Scene backdrops** — A generated picture of the room behind the story, built
  from the room's description alone so no character ever appears in one, and
  cached so revisiting a place is free.
- **Pay only when you stop** — Cached pictures always show; a new one is
  commissioned only once you have settled on that beat.
- **Readability first** — The picture sits under a veil and the prose on its own
  near-opaque panel, tuned from the image's own brightness.
- **Room continuity** — Optionally, a room's later pictures are edits of that
  room's first image, so furniture and camera angle stay put instead of being
  reinvented. Off by default.
- **Room ambience** — A looping sound bed chosen from the room's description
  alone, following the hour, the weather and any damage, from a folder of your
  own audio or Freesound's Creative Commons library. What the room actually has
  in it — a hearth, a fountain, a bank of consoles — leads the search, ahead of
  the adjectives, because that is what a place is heard through; a fire going
  out is a new sound rather than the same room reworded.
- **Nothing rather than the wrong thing** — A sound library is searched by
  narrowing, and a search that comes back with something is not the same as a
  search that came back with your room. Candidates that answer neither the room
  nor what was asked for are refused instead of laid down as better than
  nothing.
- **The mix** — Room tone, weather and one detail as separate layers, each with
  its own level, its own reroll and its own uploader credit and licence link.
- **Silence is an answer** — A room judged to have no continuous sound of its own
  says so, and you can overrule it.
- **Pin a sound** — Search by plain description, audition candidates without
  downloading anything, then pin one or save a whole mix to that room.
- **Mute and volume beside the composer** — Instant, and sticky across rooms,
  stories and reloads.
- **Weather on screen** — Rain and snow drawn over the story for rooms that can
  see them, thinning under cover, slanted by wind, scaled by severity.
- **Lightning and thunder** — Storms flash, occasionally draw a full branching
  bolt under open sky, and the thunder arrives after the flash by a
  distance-shaped delay.

## Cards, panels and editors

- **New story wizard** — Describe your character, the other people and the
  situation in plain sentences and the app builds the persona and cast, or
  build everything by hand.
- **Character card editor** — Identity, senses, appearance, traits, values,
  beliefs, coping, abilities and starting state.
- **Per-story cards** — Tune an attached character for one story without
  touching your reusable copy or resetting that story's earned mood, memories,
  beliefs or relationships.
- **Greetings** — Flip through a character's opening scenes, edit or generate
  new ones, recover the ones an imported card came with, and start a story from
  the one you like — with the greeting kept word for word and the character's
  private setup knowledge routed to their memory rather than shown to you.
- **Persona editor and private histories** — Who you play, plus per-story
  secrets only certain people know.
- **World state and attire editors** — Direct access to the scene record and to
  what everyone is wearing, for hand-correcting something that has drifted.
- **Cast panel** — Cast, attached lorebooks, everyone's condition, host-only
  insights, multiplayer and frames in one place.

## Your data

- **Local by default** — Stories, characters, lorebooks, memories and keys live
  in one database file on your machine. Nothing is uploaded.
- **No third-party assets** — The interface loads nothing from the internet.
- **What does leave** — Only what you configure: prompts to your chosen model
  providers, an optional update check, and optional sound-library lookups if you
  turn ambience on.
- **Portable archives** — Export a whole story to one file and import it back,
  including turns, world state, timelines, memories, events, checkpoints and
  lorebooks.
- **Cast travels with it** — An exported story carries its characters and
  personas, matching them to what you have or creating them rather than
  arriving broken.
- **Card import** — Character cards as JSON or as the PNGs shared on card sites,
  in both the older and newer formats; personas the same way.
- **Cards rewritten or kept literal** — Import can keep a card as written or
  have a model expand it into the engine's richer format, with warnings when a
  card is too thin to play well.
- **Psychology gap-filler** — Fill in only the missing psychological fields on an
  older card, previewed for approval, never overwriting the author.
- **Character memory export** — Save one character's remembered experiences and
  add them into another story; always adding, never replacing.
- **Lorebook import and export** — World-info and character books from other
  apps, keeping author-disabled entries switched off; export round-trips
  exactly.
- **Whole-state checkpoints** — Every turn snapshots the world, memories,
  beliefs, lore and cast, which is what makes undo and branching real.
- **Crash-safe** — A turn lands completely or not at all, in a database mode
  that survives an abrupt shutdown.
- **One turn at a time** — Conflicting edits, deletes or branches are refused
  while a turn is generating.
- **Pipeline traces** — Export one turn's full internal record for a bug report
  and replay it offline with no model calls; fingerprints only unless you
  explicitly include the text.

## Models and cost

- **Multiple providers** — As many as you like, with presets for the major
  hosted services and for local servers, or any OpenAI-compatible endpoint.
- **Per-role models** — A different model for the director, perception,
  background characters, major characters, the narrator, utilities and
  embeddings, so you spend where it matters.
- **Fallback models** — Backups tried when the first fails.
- **Per-role reasoning effort** — Thinking off or dialled up separately per
  role.
- **Model browsing** — Pull the list a provider actually offers, including image
  models with their price band.
- **Output ceiling** — One adjustable cap on how much any single call may
  produce.
- **Prompt caching** — Repeated system prompts marked cacheable where supported,
  with cache hits logged so you can confirm it works.
- **Retries and repair** — Malformed output is retried and repaired rather than
  breaking your turn; stalls time out instead of hanging.
- **Timing and token logging** — Each call's duration, tokens and cache usage.
- **Upstream routing control** — On OpenRouter, restrict which upstream hosts may
  serve a model — a prompt-retention choice as much as a quality one.
- **Editable prompts** — Read and rewrite every system prompt, saved as named
  presets you can switch between.
- **Cost that tracks drama, not length** — Turn 2000 in a quiet room costs about
  what turn 2 cost, because no stage re-reads the whole story.

## Access and updates

- **Host sign-in** — A username and password set on first run, in a session that
  survives restarts, with the password stored only as a slow salted hash and
  failed attempts rate limited.
- **Forgotten password** — A documented restart flag wipes the account so you
  can set it up again.
- **Cross-site protection** — Pages open in your browser cannot reach the app, so
  a random site cannot read your keys or drive your story.
- **Update check** — Ask whether a newer version exists and read what would
  arrive; installing only ever fast-forwards and refuses rather than
  overwriting local changes.
