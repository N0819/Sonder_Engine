# Background Life — making extras feel like people

Status: **mostly built.** Most of §3 shipped in alpha 4.0 as the scene manager —
the batched voicing (§3.3), unbatched writing (§3.2), the single stage (§3.4),
the `place` block (§3.7), frozen personality blurbs (§3.8), the opt-in tiered
config (§3.10), the I/O contract (§3.11), co-DM-not-co-author (§3.12), and
claims-not-facts (§3.13, as `background_claims.py`).

What is **not** built: the whole digest lifecycle (§3.5), promotion conversion
and the `ambient_turns` guard (§3.6 — an active defect, not just backlog),
interim filler (§3.9), `canon_ref` (§3.8.1), the separation eval (§3.3.1), the
narrator dilution clause (§5), and both §4 follow-ons. Those are registered in
[`UNBUILT.md`](../UNBUILT.md) §6.1; this document keeps the argument for them.

Read the section text below as the original proposal — it was written before any
of this existed, and its "not implemented" framing is preserved deliberately
rather than rewritten into the past tense.

The goal this document argues for: a room should feel inhabited *whether or not
the player is doing anything*. Today it only feels inhabited when the player
pokes it.

---

## 0. Why this is worth priority: the engine loses to the baseline here

The engine's registered characters are the point of the whole architecture, and
they beat plain single-context LLM roleplay decisively — private perception,
real memory, minds that do not know what they were never told.

Background extras go the other way. A single LLM improvising a tavern holds
every regular in one context and plays them as an ensemble, for free, forever.
That is the *baseline*, and on this one axis the engine is **behind** it.

The cause is not an oversight, which is what makes it worth stating plainly:
**the engine applied its central discipline to the one tier that does not need
it.** Information barriers exist to stop a mind from using what it never
legitimately received. That discipline is priceless for a character with
secrets, private motives and a relationship to protect. A bystander with no
sheet, no memory and no hidden state has *nothing to protect* — so the
per-presence isolation buys almost nothing there, while costing exactly the
thing that makes crowds feel alive: an ensemble improvised in one context.

Everything in §3 follows from that reframe. The batched `scene_life` call is not
a new invention; it is **recovering the thing plain LLM roleplay is already good
at**, fenced inside a partition (`spatial.ambient_scope`) that keeps the
discipline where it actually pays. The engine should not be paying its strictest
tax in the tier with the least to protect.

Priority follows too. A missing feature is a backlog item; being *worse than the
baseline* at something the baseline does effortlessly is a defect, and it is the
first thing a player notices about a populated room.

---

## 1. What exists today

Read this section as an accurate summary of current behaviour, not a complaint.
The existing system is well-built for the job it was scoped to do.

**Discovery** (`commit.track_background_presences`) is deterministic and
LLM-free. A name becomes a tracked presence only from structured fields commit
already trusts: `dialogue_log` speakers, `state_diff.entities` with a non-inert
`kind` (deny-list `_INERT_ENTITY_KINDS`), `state_diff.positions` keys,
`director_establish`'s top-level entities on the opening turn, and
`background_react`'s own authored line. No NER over prose — later prose
*mentions* of an already-tracked name are counted, but never discover a new
one. **One presence per body**: every harvest folds an entity-id spelling back
to the entity's display name before tracking, and `_fold_duplicate_presences`
merges an id-keyed twin (or an article variant) into the display-name record on
load, so a story already carrying a split heals at its next commit. Chat 80 is
the measured case: six presences for three things, with a device's id-keyed
twin accruing its own dialogue history and its own minted human blurb.

**Record shape** per presence:

```
{first_turn, last_turn, dialogue_turns: [idx], mention_turns: [idx],
 sketch: {role_hint, station_room}, pending_reply?: {from, quote, tone,
 turn, expires_turn}}
```

**Gate** (`commit.pick_background_reactors`) is deterministic and free. A
presence qualifies independently on any of six conditions:

| condition | meaning |
|---|---|
| `flow_addressed` | director's `flow.addressed_to` named them (forced pick, bypasses cap) |
| `addressed` | player input names them |
| `char_addr` | a roster speaker aimed a hearable line at them this beat |
| `owed` | unexpired `pending_reply` from a previous beat |
| `mentioned` | named in `resolved_event` |
| `dialogue_turns` | they have ever spoken |

No qualifier → `[]` → no LLM call. This is the common case and it is correct.

Qualifying is necessary but not sufficient: **only a person may hold a
background speaking turn** (`commit._presence_speech_verdict`). The ledger says
nothing about what a name denotes, so the presence's own frozen answer decides.

**The answer is asked where a model is already looking.** `blurb_mint` visits
every newly tracked presence once, batched per room, with the place, the
Director's description and the story's genre in front of it — so it now settles
`nature` (`person` / `thing` / `voice`, `schemas.PRESENCE_NATURES`) at no
additional call, and the answer is frozen on the record beside the blurb. A
`thing` or a `voice` is stored with no personality at all, because the stored
blurb is what made chat 80's ceiling-mounted suppression device sound like
somebody who "refuses to blink or shift posture" before it interrogated the
restrained player twice. That prompt used to open "you give personalities to
background PEOPLE" and was handed a list assembled by name; it answered the
question it was asked.

Everything below the frozen answer is a fallback for a presence that has none
yet, and is deliberately graded rather than confident: an animate kind or no
entity record at all is a person; a bodiless voice (`scene.is_ubiquitous_entity`)
or a thing (`_is_inert_presence_candidate`) is the Director's own mouth and
never speaks here; a kind that decides neither ("device" cannot be lexically
told from a "dalek war machine") speaks only on the Director's explicit
judgment this beat — `routed_to_background` or `flow.addressed_to`. **An
unanswered `nature` is not a yes**: reading an unasked question as "person" is
the defect this closes.

The kind lists (`_INERT_ENTITY_KINDS` at 50 entries, `_ANIMATE_ENTITY_KINDS` at
35) are that fallback and nothing more. They were never going to finish — the
space of nouns a story can invent has no end, and a `kind` is a word the model
chose in passing rather than a fact about the thing.
The scene-manager roster (§3.10) applies the same rule more strictly — persons
only — because the manager voices its roster with no per-signal gate.

**Reaction** (`agents/background.py:background_react`) makes one LLM call per
picked presence (cap 1, hard-ceiling 3 via `scene.background_config`). Payload:
`{entity: {name, role_hint, station_room}, beat: {resolved_event,
addressed_by, player_declaration, present_others}}`. The beat is
perception-filtered (`_beat_for_presence`, `_filtered_player_declaration`):
concealed lines dropped, unhearable lines dropped by `hear_level`, concealed
quote bodies redacted out of the objective prose. Output is at most one line and
one brief action.

**Merge**: entries are appended to the dialogue log inside
`agents/perception.py` (not by mutating `director_resolve`, deliberately — see
the comment at the merge site), so hear-level scoping, concealment and the
narrator's `_ordered_beat_events` all apply for free.

**Promotion**: `dialogue_turns >= 2` (or `mention_turns >= 4`) makes a presence
promotable; `>= 3` dialogue turns plus activity this beat auto-promotes one per
beat into a real character with a sheet and memory.

---

## 2. Why they still read as props

Five structural reasons, in rough order of how much they cost.

### 2.1 Every trigger is a mirror of the player

All six gate conditions are downstream of the player or of the director's prose
*about the beat the player caused*. There is no condition that means "this
person has their own reason to make noise right now."

That is precisely the wrong shape for the effect we want. What makes a place
feel inhabited is **indifference** — two dockworkers arguing about a debt that
has nothing to do with you, a barkeep telling someone else the kitchen's closed.
An extra who only ever exists in response to you is, structurally, a vending
machine.

### 2.2 Amnesia was applied one notch too broadly

Refusing extras memory, psychology, mind-models and relationships is right —
that is what promotion is *for*, and it is the engine's central information
discipline.

But the current design also denies a presence **its own previous public
utterance**, which is not memory of the world. It is replay of something already
committed to the dialogue log and already shown to the player. The barkeep can
answer the same question on turn 4 and turn 9 with two different attitudes and
two different registers, and nothing in the system notices.

The insight worth building on: **continuity is not interiority.** Most of what
makes a person feel real across encounters is consistency of *surface* — how
they talk, what they call you, the thing they always complain about. That can be
delivered from their own public record, at no information-barrier cost.
Interiority stays behind the promotion wall where it belongs. §3 builds the
whole design on this line.

### 2.3 They have no place

`station_room` in the payload is a bare **room id string**. Not the room's name,
not its description, not `scene.location`, not `scene.time`, not the
`fiction_model` genre, not the style guide.

So the entire location-theming budget for a background line is 160 characters of
`role_hint` harvested from the director's entity description. A barkeep in a
cyberpunk dive and a barkeep in a Regency inn receive functionally identical
context. This is the single biggest lever available and it is nearly free.

Note the style-guide exclusion in `scene.py` (`STYLE_GUIDE_FIELDS` reaches only
the Director and mapping; character agents are excluded so that "every mind in
the world" doesn't sound like the narrator). That rationale protects *authored*
characters with their own voice. A background presence has no authored voice —
it is engine-generated set dressing with a mouth, which is exactly the category
the style guide says it governs ("anything the engine GENERATES"). Extending the
guide to background presences is arguably fixing a mis-drawn boundary, not
loosening a policy.

### 2.4 One at a time, and mutually blind

At `cap > 1` each reactor is called separately, blind to the others, and the
prompt forbids referencing anyone else present. The comment in
`background_react` is explicit about the tradeoff and it is a defensible one for
*reactions*.

But it structurally forecloses the single most recognizable signature of an
inhabited room: two extras talking **to each other**. No amount of tuning the
reaction path produces that, because the architecture guarantees each voice is
generated in ignorance of the other.

### 2.5 Population depends on the director bothering

Presences only exist if the director writes structured entity defs or voices
someone in `dialogue_log`. The mapping stage mints rooms and lore for new space
but no people. So a freshly generated tavern is architecturally empty, and stays
empty until the director happens to invent someone.

---

## 3. The design: short-context furniture with a rolling digest

The shape below supersedes an earlier draft of this document that proposed
per-presence reaction calls plus a separate ambient stage. The core idea —
**give each background presence a bounded rolling summary of what it heard and
said, and let ONE call voice the whole room** — is both cheaper and better, and
it collapses two proposed stages into one.

### 3.1 The tier this creates

The engine currently has two tiers of mind: **amnesiac extra** (no memory, one
stateless beat, `agents/background.py`) and **promoted character** (sheet,
`memories` rows, mind-models, relationships, consolidation). Nothing in between.
That gap is why extras read as furniture and why promotion feels abrupt.

The digest is the missing middle tier: **continuity without interiority.** A
presence accumulates a bounded prose summary of its own perceptual slice — what
it heard, what it said — and nothing else. No mind-models, no relationship
tracking, no salience/confidence structure, no `memories` rows, no consolidation
scheduler. One short string per presence.

Three fields make up the tier, and keeping them **separate by provenance** is
what makes the whole design auditable. They are not interchangeable prose:

| field | provenance | mutability | may be batched? | §
|---|---|---|---|---|
| `blurb` | **invented** — who they are; contains no perceptual content | frozen at mint | **yes** — nothing to cross-contaminate | 3.8 |
| `digest` | **derived** — compression of committed, filtered perceptual slices | append + periodic compaction | no | 3.5 |
| `interim` | **fabricated** — offscreen filler for time the player missed | soft, low-confidence, replaceable | no | 3.9 |

Never merge them into one string. The moment fabricated filler is
indistinguishable from derived perception, the promotion path (§3.6) launders
invention into a real character's memory.

### 3.2 The cardinal rule: voice batched, write unbatched

**This rule is not a claim that the model cannot separate who knows what.** A
capable model given explicit per-presence knowledge tags in one context does
that job well (see §3.3.1 — the payload should lean on it, and the partition
rule below is an optimization, not a safety boundary). The rule is about what
happens on the fraction of occasions it slips, and that depends entirely on
where the output goes.

The risk of running N presences through one LLM is really two risks with very
different blast radii:

| | what leaks | cost |
|---|---|---|
| **Transient** | presence B's *spoken line* is colored by presence A's digest | one bad line, this turn, gone next turn |
| **Persistent** | the shared call also authors the digest updates, so the leak is written to storage | compounds forever |

Therefore:

- **Voicing is batched.** One call per turn per ambient scope, holding every
  presence in that scope. Accept transient contamination — see §3.3 for why it
  is small.
- **Writing is never batched.** A digest is extended by appending
  `_beat_for_presence(name)` output — already concealment-filtered and
  hear-level-filtered, deterministic, LLM-free. Periodic compaction runs
  **per presence**, one presence per call.

Storage never sees a shared context window. That single rule is the difference
between an acceptable tier relaxation and a slow poison.

**The asymmetry is error economics, not model capability.** Take any separation
reliability *p*. Applied to speech, a slip costs one line that is gone next
turn, so errors stay at rate *(1-p)* forever — a 99%-reliable model gives you
one odd line per hundred turns, which is beneath the noise floor of fiction.
Applied to storage, a slip is *written down, re-read on every subsequent turn,
and folded into the next compaction* — so errors accumulate, and worse, a
leaked fact in the digest is indistinguishable from a perceived one and will be
faithfully preserved by every future compaction pass. Over a 100-turn chat the
same model yields ~1 transient oddity versus ~1 permanent corruption per
presence. The gap is not about how good the model is; it is about whether
mistakes decay or compound.

### 3.3 Why batched voicing is safer than it sounds

Presences in one room have **nearly identical information sets by
construction** — they heard the same beat. The leak surface is proportional to
the *divergence* between their digests, not to digest size. Divergence has
exactly four sources:

| source | handled by |
|---|---|
| different rooms | **partition rule**: batch only presences inside the same `spatial.ambient_scope` |
| concealed lines | `_beat_for_presence` already drops them before they can be appended |
| unhearable lines | `_beat_for_presence`'s `hear_level` check, same |
| different arrival turns | *residual* — see below |

The partition rule is the important one, and it is cheap: group presences by
ambient scope, one call per group. In practice the player is in one place, so
this is one call.

The residual is arrival-time divergence — the regular who has been there since
turn 1 versus the one who walked in at turn 15 — and the honest answer is that
this is a **tier-appropriate** leak. A barfly knowing the tavern's gossip is
approximately correct barfly behaviour. The engine's information discipline
should be tiered by what a breach costs: a promoted character leaking a secret
is fatal to the premise; furniture leaking ambient common knowledge is not.

What stays **absolute at every tier**: a concealed line never enters any digest,
and never reaches any voicing call. That floor is enforced deterministically,
before the model sees anything, by the filter that already exists.

#### 3.3.1 Lean on the model's separation, then floor it deterministically

The framing above treats divergence as something to *minimize* by partitioning.
That is too pessimistic. A capable model given explicit per-presence knowledge
in one context tracks who-knows-what well — this is not a hard task for a strong
model, and designing as though batching automatically means bleed leaves real
capability unused.

So the payload should **ask for separation instead of engineering around it**:

```
"cast": [ { name, blurb, digest, present_since, knows: [...], not_privy_to: [...] } ]
```

with an explicit instruction that each speaker may draw only on their own entry.
Three consequences, all of them improvements on the draft above:

- **The partition rule demotes to an optimization.** Batching by
  `spatial.ambient_scope` stops being a safety boundary and becomes a way to
  keep payloads small and lines locally relevant. Cross-scope batching becomes
  available when it saves calls.
- **Arrival-time divergence stops being a tolerated residual.** `present_since`
  is a tag the model can honour, rather than a leak to be excused as
  tier-appropriate.
- **The tier can hold genuinely divergent knowledge.** An extra who witnessed
  something the others did not, a servant who overheard one line — these become
  expressible instead of being flattened into "everyone in the room knows the
  same things." That is *more* life, and it is the interesting version of this
  feature.

**But floor the one case that matters, deterministically.** This codebase's
recurring lesson — stated in `AGENTS.md`, and the reason `background_react`
exists at all — is that prompt compliance degrades under sustained narrative
pressure. Note the *shape* of those failures though: a model omitting an
instruction over many turns, fixed by a deterministic backstop rather than by
abandoning the prompt. Same pattern applies here.

The high-value leak is uniquely checkable because concealed content is known
**verbatim**: the engine holds the exact quote bodies it withheld. So after the
batched call, string-match every produced line (and every digest append) against
the redacted bodies and drop any entry that reproduces one. This is the same
technique `_beat_for_presence` already uses when it does
`resolved.replace(body, "")`. It costs nothing, requires no semantic judgement,
and makes the hard floor independent of model reliability entirely.

Semantic paraphrase of a secret slips past this, of course — but the floor
catches the verbatim case, and the tier argument covers the rest.

**This is an empirical question, so measure it rather than arguing it.** Before
building `scene_life`, write a small eval: construct N presences with
deliberately divergent knowledge (one witnessed a theft, one arrived late, one
was whispered to), run the batched call across several models, and string-check
the outputs for tokens only one presence should have had. That produces a real
leak rate, which decides both the partition rule and how large N can safely
get — and it is cheap to build compared to the stage itself.

### 3.4 One stage, not two

Once voicing is batched, **reaction and ambient chatter stop being separate
problems.** The earlier draft split them only because per-presence calls made
ambient life cost N calls; batching removes that pressure.

A single `scene_life` stage. It sits *alongside* `background_react` rather than
replacing it — see §3.10, where the default-off setting's `ambient` level keeps
the existing per-presence path for directed conversation and uses the group call
only for common-knowledge scene life:

```
payload = {
  "place":  { room_name, room_desc, location, ambient_location, time,
              genre, style: {genre, tone, avoid} },       # see §3.7
  "beat":   { resolved_event, player_declaration },       # existing filters
  "cast":   [ { name, role_hint, station_room, digest,
                addressed_by, present_since, last_spoke } , ... ],
  "variant_seed": nonce,
}
->  { entries: [ { speaker, quote?, action?, addressed_to?, volume } ] }   # 0..N
```

Some entries answer the player; some are two presences talking to each other.
That second kind is impossible in the current architecture — reactors are
generated blind to one another (§2.4) — and it is the single most recognizable
signature of an inhabited room.

Deterministic post-validation, mirroring what `_react_one` already does:

- `speaker` must be a name in this call's group, else drop the entry;
- an entry whose `addressed_to` is not the player is **ambient** — drop it if it
  names the player or persona in its quote;
- force `visibility: "overt"`, clamp `volume`, cap total entries (2–3);
- validate and drop entries **individually**, never fail the whole stage on one
  malformed entry.

Merge exactly where `background_react` merges today (`agents/perception.py`), so
hear-level scoping, concealment and `_ordered_beat_events` keep working
unchanged.

### 3.5 Digest lifecycle

**Append (every turn, free).** For each presence in scope, append
`_beat_for_presence(name)` output plus its own authored line to a raw ring
buffer on the presence record:

```
"digest":  "compacted prose, capped ~600 chars",
"recent":  [ {turn, text}, ... ],     # raw tail, max k entries
"digest_through_turn": idx,
```

**Compact (rare, one call per presence).** When `recent` exceeds k, fold
`digest + recent` into a new digest and clear the tail. Mirror
`memory.consolidate_character_memory`'s contract rather than inventing one: it
already implements `previous_summary` + only-what-is-new-since-`end_turn_idx`,
which exists precisely to stop payloads growing without bound across a long
chat. Summary-of-summary rot is real but bounded here, because the digest is
capped, the presence is shallow, and the raw tail is always uncompacted.

**Freeze while unobserved.** Digests tick only while the presence is inside the
player's ambient scope. A barkeep in a tavern the player left three days ago
does not accumulate — the digest freezes, and the gap is filled on return by the
separate `interim` mechanism in §3.9 rather than by silently pretending no time
passed.

**Prune.** A seeded presence that has never spoken and has not been in scope for
N turns is dropped, or the presence dict grows without bound.

### 3.6 Promotion gets better, not blurrier

The obvious objection — "if furniture has a digest, what does promotion mean?" —
inverts on inspection. `promote_background_character(cid, name, sheet=None,
memory_seeds=None)` **already accepts seeds**. Today
`auto_promote_background_characters` mints a near-blank sheet at exactly the
moment a presence became interesting enough to matter. With digests, the digest
*is* the seed material: furniture that earns a mind arrives with a history
instead of amnesia.

Promotion therefore stays the same boundary it always was — the point at which
someone gains **interiority** (psychology, mind-models, relationships,
perception as a real observer). The digest is surface continuity only, and
crossing the line converts it rather than duplicating it.

Each field converts differently, and the typology in §3.1 is what makes that
possible:

- **`blurb` → the sheet.** The frozen blurb (§3.8) seeds voice and manner
  directly. This fixes a real current defect: today promotion mints a sheet from
  scratch, so a barkeep the player has been drinking with for twenty turns can
  come back from promotion as a *different person*. A frozen blurb makes the
  promoted character continuous with the extra.
- **`digest` → memory seeds.** Derived from committed, filtered perception, so
  it converts as ordinary autobiographical seed material.
- **`interim` → low-confidence belief, or nothing.** Fabricated content must
  never convert to fact. The `memories` table already carries `provenance`,
  `confidence` and `salience` (see `consolidate_character_memory`'s payload) —
  that is exactly the right layer for it. Dropping `interim` entirely at
  promotion is also a defensible choice.

**Guard the threshold.** Digest-fed ambient chatter must not accrue
`dialogue_turns` (`AUTO_PROMOTE_DIALOGUE_THRESHOLD = 3` — three turns of
barfly noise would clear it). Ambient entries increment a separate
`ambient_turns` counter excluded from both promotion thresholds. Speaking **to
the player** is what earns a mind.

### 3.7 The `place` block (do this first, independently)

Regardless of everything above, the payload's only location context today is
`station_room` — a bare room id — plus 160 characters of `role_hint`. Add:

```python
"place": {
    "room_name":        sc["rooms"][station_room]["name"],
    "room_desc":        sc["rooms"][station_room]["desc"],
    "location":         sc.get("location"),
    "ambient_location": _ambient_location_for(sc, station_room),  # perception.py
    "time":             sc.get("time"),
    "genre":            fiction_model(cid)["genre"],
    "style":            {k: style_guide[k] for k in ("genre", "tone", "avoid")},
}
```

Every field is objective self-locating knowledge — you know what room you are
standing in. Reuse `perception._ambient_location_for` rather than reading
`scene.location` raw, so nesting rules hold identically to how they hold for
real characters. Only `genre`/`tone`/`avoid` from the style guide;
`director_notes`/`mapping_notes` are instructions to other stages, not to a
person in a room.

This is ~30 lines, needs no schema or pipeline change, and is the entire
location-theming lever. Ship it before building the digest.

### 3.8 Personality blurbs: authored once, then frozen

`sketch.role_hint` today is 160 characters of the **director's description** —
externally observed appearance and function ("a heavyset man behind the bar").
That is what a presence *looks like*, not who they are, and it is why two extras
in the same room are interchangeable.

Mint a short **blurb** for each presence the first time it is tracked:

```
"blurb": {
    "manner":  "clipped, never finishes a sentence",   # speech register
    "trait":   "resents the new management",           # one standing concern
    "tell":    "polishes the same glass",              # one repeatable physical tic
}
```

Four properties make this work:

**Frozen.** Written once and never rewritten. Immutability *is* the feature —
recognizability across turns is exactly what a re-derived-each-time personality
cannot provide. Contrast `sketch.role_hint`, which is currently overwritten
every time the director restates the entity, so a presence's identity drifts.

**Batchable.** A blurb contains no perceptual content — it is invention about a
person, not a record of what they heard. So it is the one write that may safely
share a context window with other presences, and this follows from §3.2's rule
rather than excepting it: that rule protects *derived* content. One call mints
blurbs for a whole newly-populated room.

**Style-governed.** Mint under the §3.7 `place` block: genre, tone, `avoid`, and
the room description. This is where "location-themed" actually gets decided — a
Regency innkeeper and a cyberpunk bartender diverge here, not in the reaction
prompt.

**Surface, not interiority.** A blurb is public affect — how someone comes
across to anyone in the room. It is not a private goal, a belief about another
character, a relationship, or a hidden motive. That line is the same one
promotion guards, and the blurb stays firmly on the observable side of it.

*Risk — cast homogenization.* One call minting a whole room produces a matched
set of archetypes (the gruff one, the chatty one, the sad one). Mitigate by
passing the existing presences' blurbs as **negative** examples ("do not reuse
these registers"). Cheap, and it also keeps a long-running location from
accumulating five variations on the same person.

#### 3.8.1 Canon-referenced blurbs

When the fiction *is* a known setting, a thematically-right extra is often a
recognizable one — a Ferengi barkeep in a Star Trek game, a Nazgûl-shaped rider
on the road. The blurb schema should be able to say so:

```
"canon_ref": "Ferengi barkeep, Quark register — acquisitive, obsequious, sly"
```

This is deliberately in tension with a standing engine rule. `prompts.py` tells
both the greeting interpreter and the mapping agent to treat names as opaque and
*"Do NOT import facts, identities, technology"* from outside canon. That rule is
right and should stay — but read what it protects against: the engine **drifting
into borrowed canon unbidden**, inventing a world it was not asked for. An
author who has explicitly set the game in a known setting is not that failure
mode; they are the opposite of it.

So the licence is **authorial and opt-in**, never inferred:

- It lives in the **style guide** — the existing mechanism for the author's
  standing instruction about anything the engine generates, already plumbed to
  mapping and the Director, and extended to background presences by §3.7.
- With no such licence, the current no-import rule stands unchanged. The blurb
  minter must not decide on its own that a tavern is Middle-earth.

**Register, not biography.** Even under licence, a `canon_ref` should carry
*manner, role and register* — what a model reliably knows and what a blurb is
for — and not canonical **facts**: dates, relationships, plot events, who
betrayed whom. Facts are where confabulation lives, the player usually knows the
source better than the engine does, and worst of all a fact entering the digest
becomes indistinguishable from something the presence actually perceived (§3.1).
A costume is safe; a borrowed history is not.

**Recognition raises expectations — so make it a promotion accelerant.** This is
the real design problem, and it is not the canon rule. A player who recognizes
someone expects depth immediately, and a frozen blurb with one line per beat
cannot meet that. Rendering a recognizable figure as permanent furniture is
*worse* than not having them.

Treat `canon_ref` as a strong signal the presence deserves a mind:

- lower the promotion threshold for a canon-referenced presence, or promote on
  first direct player engagement rather than at `dialogue_turns >= 3`;
- pass `canon_ref` to the sheet minter so the promoted character *is* the
  intended figure rather than a generic barkeep who happens to share a room with
  the memory of one;
- route it through the **existing review surface** — `/api/chats/{cid}/
  promotions/draft` → `/confirm` (`app.py`) already lets a human read and edit a
  drafted sheet before it attaches. That is precisely where borrowed canonical
  facts should enter: deliberately, once, under authorial review — not
  accumulated turn by turn into a digest nobody approved.

The resulting behaviour is the right one: the recognizable barkeep is furniture
while you pass through, and becomes a real character the moment you talk to him.

*Risk — the tic becomes a catchphrase.* Frozen cuts both ways: a `tell` replayed
into every voicing call is a standing instruction to perform it, and an extra
who polishes the same glass on all fourteen turns stops reading as a person and
starts reading as a stuck animation. This is the failure mode most likely to
show up in real play, and it argues for treating the blurb as **available
colour, not a required beat** — the prompt should say the tell is something they
*may* do occasionally, and the digest (which records what they actually did
recently) is what should suppress an immediate repeat. Worth watching from the
first play session, since it is a prompt-level fix if caught early and a design
problem if the blurb schema hardens around it.

### 3.9 Time passed: interim filler on return

A frozen digest plus a resumed scene means a presence behaves as though the
player stepped out for a second when three in-world days elapsed. Fill the gap —
but the gap is largely **measurable**, so most of it should not be invented at
all.

**What is measurable (use this first).** The engine has a real clock:
`simulation_clock: {elapsed_seconds, display}` in world KV, advanced at commit
from the director's `time_delta`. And `world_events` carries `occurred_at`,
`duration_seconds` and `location_id`. So on return:

```
gap        = clock.elapsed_seconds - presence.last_seen_clock
happenings = world_events WHERE location_id ∈ ambient_scope(station_room)
                            AND occurred_at BETWEEN last_seen_clock AND now
```

Both are committed fact. Store `last_seen_clock` (and `last_seen_turn`) on the
record when the presence leaves scope.

**What is fabricated (constrain it hard).** The LLM authors only personal
routine texture over that skeleton — "the lunch rush was ugly, we ran out of
ice." Scope rules, enforced in the prompt and checked deterministically where
possible:

- **Own station, own routine only.** May not invent world events, plot
  developments, other named characters' actions, or anything concerning the
  player. A background presence does not own objective causality; the Director
  does, and this is that boundary applied to offscreen time.
- **Never contradicts `happenings`.** Real committed events at that location are
  given as fixed input, not suggestions.
- **Hard length cap** (~300 chars) and stored in `interim`, never appended to
  `digest`.

**Lazy: generate on first re-voicing, not on re-entry.** Cost is zero for the
extras the player walks past and never speaks to, and you cannot write good
filler until you know how long the gap turned out to be. Gate it on the presence
having real history (`dialogue_turns` non-empty) — furniture the player never
engaged does not need an offscreen life.

**The sharp edge: filler is the only fabrication in this design.** Everything
else derives from committed records. Two containments, both load-bearing:

1. *Promotion.* Never converts to fact — low-confidence, provenance-tagged
   belief, or dropped (§3.6). Otherwise the digest laundering path turns
   invented filler into a real character's canon memory.
2. *Speech.* The moment a presence **says** its filler out loud, the player
   treats it as fact and the Director must honour it. Keeping filler to personal
   routine at the presence's own station is what makes that survivable: an
   invented bad lunch rush costs nothing if the Director never ratifies it,
   whereas an invented visit from the town guard is a plot the Director never
   authored. Scope discipline, not tagging, is what prevents this one.

### 3.10 The scene manager: opt-in, tiered, and filtered as a group

**Off by default.** This ships behind a setting, not as new baseline behaviour.
The reasons are practical as much as cautious: it is the one component here that
relaxes an information rule, its value is a matter of taste (some authors will
find a chattering room noise), and gating it makes the §3.3.1 eval runnable
against real play without putting anyone's ongoing chat at risk. Home is
`scene.background_config(chat_id)` — already per-chat, already backed by
`wget(cid, "background_config")`, already holds `max_reactors` — with an
optional global default via `get_setting`, mirroring how `auto_promote` works.

#### The reframe: manage a place, not a list

The useful unit is **one LLM given a location and the set of presences it
manages**, asked to keep that place alive for a beat. That is a better frame
than "voice N presences" because it is what the model is actually good at, and
it is what plain LLM roleplay does well (§0).

It also invites one specific scope error that must be closed up front:
**the manager voices people; it does not change the world.** "Manage a location"
is a phrase that slides toward authoring the fire, the weather, an arriving
stranger — all of which are the Director's to own (`AGENTS.md`). The manager's
output is dialogue plus minor personal action, no `state_diff`, no world facts,
no new entities. Enforced by schema, not by prompt.

#### Group-level filtering, and why it beats per-presence filtering

Filter **once, for the managed group**, rather than per presence. The manager's
context receives:

- every **overt** line audible at the managed location (`hear_level` from the
  speaker's room), and
- a **directed or concealed** line *only* when its target is one of the managed
  presences.

It never receives whispers between other parties, lines concealed from all
managed presences, the player's concealed sequence elements, or private thought
— none of which reach the call at all, so no prompt discipline is required to
protect them.

This is a real simplification over §3.3.1's per-presence `knows` /
`not_privy_to` arrays. After group filtering, **the only divergent content left
in the context is the directed-at-one-managed-presence case** — a single, known
category rather than a general knowledge model. And it can be marked **inline,
at the content itself**:

```
{ speaker: "Player", quote: "...", audience: ["Mira"],  # Tomas did not hear this
  note: "whispered — only Mira may act on it" }
```

Marking divergence next to the thing it constrains is meaningfully easier for a
model to honour than reconciling a separate per-presence knowledge table, and it
degrades gracefully: the worst case is one extra reacting to something they
should not have heard, in a tier where that costs one line.

#### Three levels, not a boolean

The setting should expose the safety/richness tradeoff rather than hiding it:

| level | manager context | divergence in context | cost |
|---|---|---|---|
| `off` *(default)* | — | none | current behaviour |
| `ambient` | **common knowledge only** — directed lines withheld entirely | **zero, provably** | group call + existing per-presence path |
| `full` | common knowledge + directed lines, inline-tagged | one marked category | group call only |

`ambient` is the interesting middle and deserves emphasis: withhold directed
lines from the group call entirely and let a directed line fall through to the
**existing** `background_react` path, which already handles exactly that case
correctly. The manager's context then contains nothing that is not common to all
its managed presences, so cross-contamination is not mitigated — it is
*impossible*. The engine keeps the mechanism it already has for the case it is
already good at, and adds a group call only for the case it is bad at.

The price is coherence: at `ambient`, an extra answering the player and another
muttering about it come from two separate calls and will not reference each
other. `full` buys that single-beat coherence and pays the tagged-divergence
risk for it. That is a real authorial tradeoff, which is why it belongs in a
setting rather than in a decision made here.

### 3.11 The I/O contract: structured perception in, attributed conduct out

#### Perception is two layers, and only one of them is a guarantee

§3.10's group filter and per-character perception structure are not alternatives
— they compose, and it matters which one carries the guarantee:

1. **Admission control (deterministic, hard).** Decides what enters the context
   *at all*. A whisper between two other parties, a line concealed from every
   managed presence, the player's concealed sequence elements — these never
   appear, so no prompt discipline is protecting them. This layer is the
   guarantee.
2. **Per-character annotation (structural, model-honoured).** Within admitted
   content, marks *which* managed characters received *what*. This layer is
   fidelity, not safety: if the model ignores it, the failure is one extra
   knowing something mildly early, never a leaked secret — because the secret
   was never admitted in step 1.

Keeping the roles distinct is what lets the annotation be rich without the
safety story depending on it.

#### Use all three hear levels — `fragment` is the interesting one

`spatial.hear_level` already returns **`full` / `fragment` / `none`**, and the
current code throws away the middle: `_beat_for_presence` keeps only what is
audible, and `_character_address_of` requires `full` outright (reasonably — a
fragment cannot be coherently replied to *by a single reactor asked for one
line*).

Under a structured per-character input, a fragment stops being a problem and
becomes material:

```
"events": [
  { "speaker": "Player", "quote": "...", "audience": {
       "Mira":  "full",
       "Tomas": "fragment",     # caught a name and a tone, not the sentence
       "Old Hen": "none" } } ]
```

An extra who *half*-heard something and reacts to the half — mishears a name,
catches the anger but not the words, asks the person next to them what was said
— is more lifelike than one who either knows everything said in the room or
nothing. This is the kind of texture the per-presence architecture could not
express and a scene manager can.

Note this annotation is computed **deterministically** from `hear_level` /
`spatial_rel` / concealment metadata. It is not a perception LLM call per
presence — that expense is precisely what the group call exists to avoid.

#### Output: attributed conduct, one entry per acting character

```
{ "entries": [
    { "name": "Tomas",
      "speech": { "quote": "...", "volume": "normal",
                  "intended_target": "Mira", "tone": "..." },   # optional
      "action": "wipes the same glass again" }                  # optional
  ] }                                                            # 0..N entries
```

Validation before anything is used: `name` must be in the managed set (drop the
entry otherwise, individually — never fail the whole stage on one bad entry);
force `visibility: "overt"`; clamp `volume`; apply §3.4's rule that an ambient
entry may not target the player; cap total entries.

#### The append is a routing operation, not an authoring one

This is the part that resolves the apparent conflict with §3.2's "write
unbatched" rule — and the resolution is better than the rule.

The batched call never authors digest prose. It emits **structurally attributed
entries**, and deterministic commit code routes each one to its own presence's
profile: entry `name` selects the record, the quote appends to that presence's
raw tail as an own-utterance, counters update per §3.6. No shared-context
summary is ever written to storage, because the model was never asked to write a
summary at all. §3.2 stands unchanged; this just satisfies it by a cleaner
route than "one compaction call per presence."

Two conditions make the append safe:

- **Validate before append, not just before render.** §3.3.1's verbatim floor —
  string-matching output against withheld quote bodies — must run *ahead of the
  write*. A contaminated line that is merely rendered costs one turn; the same
  line appended to a profile is re-read every subsequent turn and survives every
  future compaction. This is the single most important ordering constraint in
  the design.
- **At `ambient` (§3.10) it is provably safe.** The group context holds only
  common knowledge, so a contaminated line cannot be produced, so the append
  cannot poison anything. The level structure carries through to storage safety,
  not just speech safety.

#### The new risk this creates: a self-feeding loop

Appending manager output to profiles that the manager reads next turn closes a
feedback loop. The manager gives Tomas one bitter line on turn 3, reads "Tomas
said something bitter" on turn 4, and escalates; by turn 20 Tomas is a
caricature of a mood he was never authored to have. Self-feeding summaries drift
toward their own most recent extreme, and nothing in the loop pulls back.

The **frozen blurb (§3.8) is the anchor**, and this is the strongest argument
for its immutability. It never moves, so it is the one thing in the payload
still describing who this person actually is rather than what they most recently
happened to do. Two consequences for implementation:

- compaction must be instructed to preserve the blurb's register, not the recent
  emotional trend — the digest summarizes *events*, the blurb owns *manner*;
- if drift shows up in play anyway, the cheap corrective is to cap how much
  recent material reaches the manager (a short tail plus the frozen blurb) long
  before reaching for anything cleverer.

### 3.12 Co-DM, not co-author: the manager's relationship to the Director

"A co-DM to the Director" is the right instinct, and it survives contact with
the ownership model — with one correction and one genuinely interesting
consequence.

#### Delegate, not peer

At a real table a co-DM runs a faction or a location while the primary DM keeps
the final call on outcomes. That is exactly the available role here: the manager
is the Director's **delegate for one location's populace**, not a second author
with world authority.

The correction is the one §3.10 already draws, and the co-DM framing makes it
more urgent rather than less: **the manager gets people, not events.** A DM's
single most characteristic move is "and then the door bursts open" — and that is
precisely the move the manager must never make. This is not bureaucratic
tidiness. Two agents that can both introduce world events will contradict each
other, and there is no adjudicator standing above them to reconcile it. The
Director's ownership of causality is what makes a single coherent world
possible; a co-DM who can spawn events is just a second Director racing the
first.

#### Where it sits in the pipeline is the real question

The co-DM idea gets architecturally concrete as a placement decision, and the
two options differ more than they look:

**(a) After `director_resolve`** — where `background_react` sits today. The
manager reacts to an already-settled beat. Nothing downstream adjudicates its
output, which is exactly *why* the output must be restricted to conduct that
cannot fail: speech, and minor personal action. Cheap, safe, and the right
starting point.

**(b) Before `director_resolve`** — the manager *declares* its characters'
intents, and the Director resolves them alongside everyone else's. This is the
true co-DM position, and it fits the existing model with no strain at all: the
manager becomes a **batched declaration source**, exactly parallel to the
`character:<id>` steps that declare for registered cast. Character agents
declare; the Director resolves. The manager is simply the cheap tier's version
of the former.

(b) unlocks something (a) structurally cannot: **contestable conduct.** Today a
background presence can only ever do things that cannot fail. A regular who
*tries* to block the door, grab an arm, or snatch the coin off the bar is
currently inexpressible — not because it would be unsafe, but because nothing
would adjudicate the attempt. Under (b), the Director resolves it like any other
contested act. That is a large lifelike-ness gain, and it is the single strongest
argument for the co-DM framing.

The cost is real: at (b) the manager declares *into uncertainty*, not knowing how
the beat resolves — which is correct and is what every character agent already
does, but it means (b) cannot do the react-to-what-just-happened job that (a)
does. These are genuinely two different stages at two different positions, not
one stage that can be moved. Doing both is two calls per beat.

**Recommendation: ship (a), design so (b) is reachable.** Keep the manager's
output schema shaped so that adding a `commitment: asserted|contestable` field
later is additive rather than a rewrite. Revisit (b) once the tier has proven
itself in play.

#### What this implies about the promotion boundary

Follow (b) to its end and the manager is a full declaration source whose
characters can attempt contestable acts — at which point it has quietly become a
cheap character agent. That is worth noticing, because it sharpens where the
promotion line actually belongs.

What still separates the tier from a promoted character at that point is **not
the ability to act.** It is memory depth and private psychology: real `memories`
rows, mind-models, relationships, a perception slice of their own. §3.6 already
treats interiority as the promotion boundary; this confirms it from the other
direction. "Can they do things?" is the wrong question and always was — a
bystander who can never attempt anything is not protecting an information
barrier, just impoverished.

### 3.13 Keeping the invention: claims, not facts

**Implemented** — `background_claims.py`, driven by a live result rather than a
hypothesis. See `demo/tavern_scene_life/findings.md`.

The tavern run showed the manager inventing small world facts through its
people at roughly one proper noun per turn. Verified against the Director's own
output: "Tam Briddock's boy" (t2) and "the tinker's lot last month" (t3) appear
nowhere in `director_resolve` for those turns. §3.12 says the manager gets
people, not events — so on a strict reading this is a defect.

But the same run showed why it is worth keeping. The t2 invention was absorbed
into canon, and by t6 the Director-voiced Widow says *"Ewe came back alone.
Drover's boy didn't"* — the invented detail had become the dramatic spine of the
best scene in the test. **The mechanism that makes the room feel alive is the
same one that erodes the Director's ownership.** Suppressing it costs most of
the texture.

So the fix is not suppression. It is making every *outcome* coherent.

#### The failure mode being designed out

Today's failure is **"the engine forgot it said this."** The player asks who Tam
Briddock is and nothing in the world knows: the Director never recorded it, no
lore entry exists, and the next beat either confabulates fresh or silently
denies it. That is incoherence, and it is the only genuinely bad outcome
available.

Record the claim and the three possible outcomes are all ordinary fiction:

| outcome | what the player sees |
|---|---|
| **ratified** | the Director adopts it; it is canon |
| **contradicted** | the Director establishes otherwise — the speaker misremembered, or lied. Because the *claimant* is recorded, the world can show that, which is better fiction than silence |
| **expired** | nobody followed up. It was tavern talk |

None is incoherent. That is what "robust failure" means here — not preventing
the false claim, but ensuring no branch ends in the engine contradicting
itself.

#### Mechanism

Deliberately the same shape as the Player Authority Contract in
`director_interpret`, which already records a player's claim about another
character's past words as *claimed, not established* and lets the named party
confirm, correct or ignore it. A background presence's assertion about the
world gets identical treatment for an identical reason: neither owns objective
causality.

- **Declare.** `SceneLifeEntry.asserts` — the manager lists names/details its
  line introduced that the beat did not already establish.
- **Backstop.** `novel_proper_nouns()` scans quotes for capitalized phrases
  absent from everything already in play (scene entities, rooms, positions,
  cast, persona, prior claim refs). Belt-and-braces, the standard shape here:
  ask the model to report, and check cheaply for what it failed to report.
  Note the scan is deliberately partial — lowercase lore ("the tinker's lot")
  is invisible to it, which is exactly why `asserts` exists and why the scan
  is only the backstop.
- **Record.** `record_claims()` stores `{claimant, text, refs, credence, turn,
  status, expires_turn}` in world KV, idempotent by content hash so a rerun
  does not duplicate.
- **Surface.** `unratified_claims()` rides the Director's `director_resolve`
  payload beside `engine_notices` and `due_authored_events`, bounded to 6.
- **Settle.** `settle_claims()` marks a claim ratified when the Director names
  it in `state_diff.ratified_claims` *or* writes its reference into the
  objective record — so adoption does not depend on the model remembering to
  fill a list. Unclaimed after `CLAIM_TTL_TURNS` (8), it is dropped.
- **Write.** Ratification is a *write*, not a flag. `write_canon()` puts the
  claim into `lore_entries` in the chat's own canon lorebook
  (`memory.ensure_chat_canon_book`) — the only durable store of facts
  established during play and the only one anything reads back into a prompt
  (`search_lore` → mapping's `relevant_lore` → the Director's and perception's
  payloads). For two releases this step did not exist: `settle_claims` set
  `status = "ratified"` and stopped, so a claim became true and unreachable in
  the same instant, which is the *original* failure ("the engine forgot it said
  this") displaced one step later. Keyed by the claim's own content hash so a
  replayed commit cannot mint a second row; attributed rather than paraphrased,
  because asking a model to restate it would put a second author between the
  Director's adoption and what canon ends up saying; and stamped
  `source_notes: ratified background claim …`, which is also the only way to
  count how often this lane has ever fired.
- **Contradict.** `state_diff.contradicted_claims` is how the Director records
  that a presence was *wrong*. The record is kept, claimant and all: a
  bystander who misremembers is characterization a later beat can show, and a
  rejected claim that left no trace was byte-identical to one nobody bothered
  with. A claim named in both lists is the Director disagreeing with itself; it
  settles as contradicted and writes nothing, because canon is a one-way door —
  the disagreement is recorded (`ratification_conflict`) rather than averaged
  into a half-truth.

Contradiction is **explicit only**, where adoption may also be inferred from
the objective record. The asymmetry is the point: prose naming a claim's
subject is evidence the fiction took it up, but prose can no more announce a
rejection than it can announce silence — "the Widow denies it" and "the Widow
says it again" share every distinctive token.

#### Why `CLAIM_TTL_TURNS` is not tuned per subject

The obvious worry is that a *true* claim can expire before anyone ratifies it —
and that a claim about a place ("the east wing burned") ought to outlive one
about a person, who moves. Neither is implemented, on three grounds:

1. **Every turn is a real chance.** `unratified_claims()` rides
   `director_resolve`'s payload unconditionally, not only when the player
   returns to the place a claim is about. Eight turns is eight consecutive
   declines by the sole ratifier — a decision, not a missed window.
2. **Expiry unsays nothing.** The line was spoken and stays in the dialogue log
   and the events row. What lapses is the *offer* to adjudicate, not the
   fiction.
3. **The module cannot tell a place from a person.** A ref is a bare
   capitalized phrase or a manager-declared string; classifying it would be the
   same string-guessing this design already refuses for contradiction, and a
   misclassification would silently change a claim's lifetime.

And the measurement is missing. Against the production corpus this lane has
produced **0 claims** (2,411 `background_react` variants, 39 through the
manager path, 29 that called the detector), so there is no ratification or
expiry rate to tune against. Get the rate first — the `source_notes` stamp
above is what makes it countable — then decide.

#### Credence comes from the frozen blurb

`claimant_credence()` derives how much weight the *fiction* has already given
this speaker from their frozen blurb (§3.8). The tavern old man's real blurb —
*"creaking voice, too slow for conversation, trails off mid-thought"* — yields
`low`; a careful, precise presence yields `high`.

This is what makes leaving a claim unratified safe. The player has already been
signalled how much to trust it: a rambling drunk's story reads as suspect on
sight, so it costs nothing if it is never confirmed. The unreliability is
diegetic, not a system gap.

#### What the Director is told

`director_resolve`'s prompt gains an adopt / contradict / ignore clause, with an
explicit instruction to adopt *sparingly* — a claim that would rewrite canon,
contradict an established fact, or hand the player a plot the Director did not
author should be contradicted or ignored, never adopted by default. And the
manager's own prompt bounds what may be invented: village-sized and personal
only, never the player's plot, never a place not on the map, never a large
event, never a registered character.

Precision matters here because a false positive puts noise in the Director's
payload. Two real defects from the run are fixed and pinned: a mid-quote
sentence start ("…end of autumn. **That'd** be…") is not a name, and an
article-stripped reference ("the Widow") matches the established "The Widow"
rather than inventing a second person.

---

## 4. Follow-ons

Worth building only after §3 proves the channel reads well — they exist to feed
it.

**Location-themed population at mapping time.** Let the mapping stage emit
`ambient_presences: [{name, role_hint, station_room}]` (0–3) when it mints a
room. Commit tracks them with `seeded: true` and empty `dialogue_turns` so they
do not auto-qualify to react. Mapping already receives the style guide and
fiction model, so theming is free: a tavern gets a barkeep and a regular, a
morgue gets a night attendant, a bridge gets an ensign at ops. Requires the
pruning rule from §3.5. Note this is the one genuinely new information surface
in this document — a seeded presence is a *fact about the world* mapping
invented, so it must commit through the normal scene/entity path, not be written
straight into `background_presences` behind commit's back.

**The chorus presence.** The hard-cap comment in `background_react` already
states the principle: *"beyond this a crowd is a chorus."* Make it an entity
kind — `aggregate: true` renders unattributed collective reaction ("someone at
the back laughs"), no name, no promotion path, no per-member tracking, one
digest for the whole crowd. Mapping seeds one for any room it calls crowded.

---

## 5. Remaining risks

**Narrator dilution.** Ambient entries are *texture, not beats.* The narrator
prompt needs an explicit clause that they may be compressed, rendered as
overheard fragments, or folded into a sentence of atmosphere — never dramatized
as the turn's event. Suppress the ambient half of `scene_life` entirely on
high-tension beats (a contested reaction ran, a weapon came out). Without this,
every quiet turn inflates into a set-piece and pacing dies.

**Rerun / variant determinism.** `scene_life` must be a real `steps`/`variants`
row like every other stage, and any cadence gating must be a pure function of
`(chat_id, turn_idx)` — no wall clock, no RNG — or rerun-from-stage and reroll
silently change whether the room was alive. Digest appends happen at commit,
inside the turn transaction, so a rolled-back turn does not leave a half-written
digest.

**Digest as a leak vector.** The content is not the danger; the **provenance**
is. Appending `_beat_for_presence` output is safe by construction. Appending
`resolved_event` raw, or any other observer's perception view, is not — the
first is authored from the omniscient objective frame, which is exactly what
`_beat_for_presence` exists to filter. This invariant deserves a test.

**Cost.** One call per turn per occupied ambient scope, plus a rare compaction
call per presence. Compare to today: zero on quiet turns, one per picked
presence otherwise. The gate should still skip `scene_life` entirely when the
scope holds no presences, so empty rooms stay free.

---

## 6. Sequencing

1. **`place` block** (§3.7) — smallest diff, immediate qualitative win, no
   schema or pipeline change. Evaluate before building anything else.
2. **Blurbs** (§3.8) — one batched mint call at tracking time, frozen
   thereafter. Independent of everything below it, and on its own it already
   makes two extras in one room distinguishable. Highest ratio of felt effect to
   implementation cost in this document.
3. **Digest storage** (§3.5, append + freeze + prune) — deterministic, LLM-free,
   no behavioural change yet. Land it and let digests accumulate in real play so
   step 4 has material to test against. Record `last_seen_clock` here even
   though nothing reads it until step 6.
4. **Per-presence compaction** (§3.5) — mirror
   `memory.consolidate_character_memory`'s incremental contract.
5. **The separation eval** (§3.3.1) — measure the real cross-presence leak rate
   before committing to a partition rule or an N. Cheap, and it decides design
   questions that are otherwise settled by argument.
6. **`scene_life`** (§3.4, §3.10) — the batched scene-manager stage, **added
   alongside `background_react` rather than replacing it**, and **off by
   default**. Ship the `ambient` level first: its group context is
   common-knowledge-only, so it needs no separation guarantee at all, and
   directed lines keep falling through to the existing per-presence path. Add
   `full` only if the §3.3.1 eval supports it. Needs a new prompt, schema entry,
   group filter, post-validation, and narrator clause; tests mirroring
   `tests/test_background_react.py` and `tests/test_background_beat_filter.py`;
   plus new ones for the §5 provenance invariant, for ambient entries never
   accruing `dialogue_turns`, for the group filter withholding every whisper and
   every line directed at a non-managed party, and for §3.11's ordering
   constraint — that the verbatim floor runs *before* the profile append, not
   only before rendering.
7. **Interim filler** (§3.9) — last, deliberately. It is the only fabricating
   component, and it is worth building only once the derived layers work, so
   that its output is visibly distinguishable from theirs in real play. Needs a
   test that `interim` never reaches promotion as fact.
8. **Follow-ons** (§4).
