# Background Life — making extras feel like people

Status: **design / theorycraft only**. Nothing here is implemented. Written after a
read of `agents/background.py`, `commit.py`'s presence-tracking and gate code,
`prompts.py:background_react`, and the merge sites in `agents/perception.py` /
`agents/narration.py`.

The goal this document argues for: a room should feel inhabited *whether or not
the player is doing anything*. Today it only feels inhabited when the player
pokes it.

---

## 1. What exists today

Read this section as an accurate summary of current behaviour, not a complaint.
The existing system is well-built for the job it was scoped to do.

**Discovery** (`commit.track_background_presences`) is deterministic and
LLM-free. A name becomes a tracked presence only from structured fields commit
already trusts: `dialogue_log` speakers, `state_diff.entities` with a non-inert
`kind` (deny-list `_INERT_ENTITY_KINDS`), `director_establish`'s top-level
entities on the opening turn, and `background_react`'s own authored line. No NER
over prose — later prose *mentions* of an already-tracked name are counted, but
never discover a new one.

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

### 3.4 One stage, not two

Once voicing is batched, **reaction and ambient chatter stop being separate
problems.** The earlier draft split them only because per-presence calls made
ambient life cost N calls; batching removes that pressure.

A single `scene_life` stage, replacing `background_react`:

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
5. **`scene_life`** (§3.4) — the batched stage replacing `background_react`:
   new prompt, new schema entry, partition rule, post-validation, narrator
   clause. Needs tests mirroring `tests/test_background_react.py` and
   `tests/test_background_beat_filter.py`, plus a new one for the §5
   provenance invariant and one asserting ambient entries never accrue
   `dialogue_turns`.
6. **Interim filler** (§3.9) — last, deliberately. It is the only fabricating
   component, and it is worth building only once the derived layers work, so
   that its output is visibly distinguishable from theirs in real play. Needs a
   test that `interim` never reaches promotion as fact.
7. **Follow-ons** (§4).
