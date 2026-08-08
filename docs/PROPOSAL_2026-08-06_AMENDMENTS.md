# Amendments to PROPOSAL_2026-08-06 — as of 2026-08-08

What changed after the proposal was written, and why. Everything here came out
of measurement or a decision, not revision for its own sake; the proposal
itself is left as written so the two can be read against each other.

Evidence marking follows the parent document: `[measured]` means a query
against a live database, `[read]` means the code was opened.

---

## 1. The build order changed. 0c is now first.

The proposal's §6 ordered: 0a provisional tier, 0b out-of-band queue, then item
1 (gap generator), with subject identity (§2A) as item 4-ish and `signal_id`
after it.

**New order: 0a, 0b, 0c (subject identity), then item 1.**

The proposal already contained the argument and did not schedule for it. §2A:
*"everything downstream resolves people, and it is resolving strings"*; §1.2
step 1 property 1 requires `subject.id` to be an id rather than a display name.
So **the gap generator cannot satisfy its own first stated property until
subject identity exists** — a dependency, not a preference.

The measurement settled it `[measured]`: of 38 `background_presences` rows
across 19 chats, against 500 scene entity rows —

| | count |
|---|---|
| exact case-folded match | 18 (16 chats) |
| differing only by article or title | 2 (1 chat) |
| absent from `scene.entities` under any normalisation | **18** (7 chats) |

Resolvable floor **20/38 = 52.6%**. Note the correction this forced: the gap
was read first as the article/title defect (the "A Dalek / Dalek / The Dalek"
shape). It is mostly not — 2 of 38. Eighteen were never entities at all, which
is a different repair.

## 2. `signal_id` stays after item 1, with a trigger rather than a slot.

Nothing in the gap generator needs it, and it is the cheaper of the two
identity retrofits. Per the proposal's own rule that *a retrofit with no date
is a retrofit that does not happen*, it gets a written trigger: **the next time
anything new is minted that would carry one.**

## 3. The reservation ("a tick may never take the last slot") is not an item.

Proposed during this work and killed by census `[measured]`: tree-wide
`SEMAPHORE_NONTEST=0`, `BACKDROPS_BOUNDS=0`, `TPE_NONTEST=3`. The three
executors are `agents/narration.py:949` (`max_workers=len(ctx.extra_players)`),
`agents/perception.py:818` (`min(len(jobs), _PERCEPTION_FANOUT_WORKERS)`, that
constant a bare module-level 4) and `commit.py:5906`
(`max_workers=len(ctx.cast)`) — **zero settings reads among them**. A
reservation would have to create the bound it reserves within.

The argument behind it is also withdrawn. It rested on provider contention
measured on the **Assistant**, not the engine: `QUOTA_LIVE=0`,
`PERSIST_COUNTER=0`, and the 15 ratelimit sites in `providers.py` are all
reactive 429 handling `[measured]`. Sonder enforces no shared call budget.

## 4. Offscreen ticks: start on commit, run in parallel, never cancelled.

Decision. A tick in flight when the player speaks **runs on**.

The reason is not throughput. Cancelling on turn-start makes the world's
progress depend on player idleness — the more engaged the player, the less
alive the world — which inverts the feature's purpose.

## 5. Hazards 4 and 5 collapse, and dissolve.

Two hazards were proposed on top of §1.0.2's three: a worker still in flight
when the player quits, and the player walking into the subject a tick is about.
They are one defect: *an offscreen assertion landing during or after the
player's observation of its subject.*

And the resolution removes the need for cancellation rather than implementing
it: **if an offscreen tick may only write provisional assertions, arrival is
the resolution event rather than the collision.** The player walking in is what
settles the claim, not what breaks it.

Falsifier, held at working-theory strength: if any tick path writes directly
into canon rather than a provisional pool, arrival-time resolution is
impossible and cancellation returns.

## 6. The frame: coherence is a retrieval problem before a generation problem.

The binding constraint on offscreen richness is not cost — the engine has no
shared budget (§3). It is **whether the engine can find an offscreen assertion
again, keyed to the right subject, at the moment the player arrives.**

This is the amendment that most changes what 0a is for. It makes 0a's
validator and 0c's identity work the product rather than the bookkeeping.

## 7. 0a's promotion target: **the Director promotes.** (Decided.)

The proposal named exactly one status value, `provisional`, and no promotion
target — no statement of what a corroborated row becomes, who writes the
transition, or where it lands. That hole is now closed by decision: adjudication
explicitly ratifies or contradicts.

**Most of the path already exists** `[read]`:

- `prompts.py:1833` instructs the Director to name a claim in
  `state_diff.ratified_claims` — *"it becomes canon and the world must honour
  it"*.
- `schemas.py:1609` carries `ratified_claims: list[str]`.
- `agents/director.py:3428` places `unratified_claims` **into** the Director's
  payload (called at :3075, not merely imported).
- `commit.py:3303` passes `state_diff.ratified_claims` to `settle_claims`.

**What is missing is one write.** `settle_claims` sets `rec["status"] =
"ratified"` in the world-KV blob and writes nothing into canon. The prompt
promises canon; the code sets a flag.

`contradicted` stops being decorative under this decision — the Director
contradicting is now a real path, and that state is documented in
`background_claims.py`'s own comment and never written.

**Consequence not yet designed:** promotion at adjudication combines with the
inclination to *batch* adjudication at re-contact, so a claim can sit
unratified for many turns while being true — and `CLAIM_TTL_TURNS = 8` deletes
it first. Either the countdown pauses while a subject is offscreen, or
place-claims and person-claims need different lifetimes. A claim about a person
goes stale because people move; *"the east wing burned"* does not.

## 8. Ungenerated locations are a third subject kind.

A lorebook place the mapping agent has never generated has no `room_uid`, so it
cannot be a `room` subject. It needs `kind: place`, keyed on the lore entry.

Design: **do not simulate it; let it accumulate obligations.** Nothing about the
place is computed while the player is away. What is recorded is that the letter
went there, the garrison moved through, the fire happened — as unratified
claims. When the mapping agent finally generates the room, it is generating a
room that **owes a history**, and the accumulated claims are the constraint.
Zero cost while absent, and the expensive step is one already being paid at
arrival.

The cheapest immersion lever on top of it is **reference before arrival**,
riding on dialogue that already happens — with the inversion that the mention
*creates* a claim the room must honour, rather than prose having to stay true
to state.

Bar to clear first `[measured]`: 421 place-marked lore entries across 48 chats
have no `room_registry` row and no scene-blob appearance, and at most **18** of
those 421 are ever named in narrator or director prose for the same chat —
**≤4.3%**, where 18 is a ceiling and 421 a floor.

## 9. The claims lane has never fired, and the denominator is 29.

The load-bearing dependency of §7 and §8 has never run `[measured]`:

```
2,411  background_react variants
1,401  carry a "mode" key   (1,010 predate the signature and cannot testify)
   39  carry scene_life in mode   → gate 1 and gate 2 both passed
   29  of those carry "fired": true AND a non-empty reactions list
    0  carry "claims"
```

**29 is the opportunity count** — not 1,200 (`background_react` *steps* after
the emitter landed) and not 2,411. Both larger figures were used at some point
and both are wrong; the rule that catches it is in §11.

The emitter is wired, not orphaned: `res["claims"] = claims` at
`agents/background.py:529` under `if claims:`, one site tree-wide, with
`GUARDS=0` between `track_background_presences`' entry and the `record_claims`
call. Both it and `_claimed_refs` entered in commit `7b5b0fe`, 2026-07-25, so
this is a live gate that has never opened rather than absent code.

**What the corpus cannot say, and why.** `_claimed_refs` computes
`declared + detected` and stores neither; `agents/background.py:517` builds
reactions as `{name, dialogue_log_entry, action}` only. So no stored variant
could ever carry `asserts` — the zero is a fact about storage shape, not about
the model. Four cases remain indistinguishable from the corpus: the model
omitted `asserts`; it sent `asserts: []`; either half produced candidates and
the filters ate them; entries were dropped before `_claimed_refs` was reached.
Only instrumentation and a live run separate them.

Two refuted premises worth keeping so they are not re-tried:

- **`asserts` is not stripped by the schema.** It is on `class SceneLifeEntry`
  at `schemas.py:1536`, and `SceneLifeOutput.entries` is a list of those `[read]`.
- **The prompt does request it** — `prompts.py:1809` and `:1813` `[read]`.

## 10. A separate live defect found on the way.

`DialogueLogEntry.speaker` is required with no default (`schemas.py:1508`), and
the scene_life prompt declares the shape as
`speech:{exact_quote, volume, intended_target, tone}` (`prompts.py:1813`) —
**no `speaker`** `[read]`. The model cannot send a field it was never asked
for. This killed a lab run outright and burns repair calls whenever it fires.

It is **not** the explanation for §9's zero: 27 of the 39 scene_life variants
carry a non-null `dialogue_log_entry` `[measured]`, so speech has survived
historically, presumably via the repair loop.

## 11. The rule that would have caught three errors in one evening.

> **Before quoting a count, name the write site that would have had to execute
> for a non-zero to be possible.**

It catches all three of the miscounts made while producing this document: an
`asserts` count against a storage shape that cannot hold it; a name-mismatch
proxy standing in for entity existence; and `background_react` steps standing
in for claim opportunities. For claims the write site is the single `if claims:`
at `background.py:529` and it does execute — which is what makes 0-of-29 a real
finding rather than an artefact.
