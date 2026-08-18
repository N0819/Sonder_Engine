# Directive on Sonder — post-gap hardening report

**Audience:** Sonder Engine maintainer

**Purpose:** document two robustness improvements identified after Sonder
implemented the remaining Directive integration gaps

**Reviewed against:** Sonder alpha 9.4 (`af12375f`), 2026-08-18

**Predecessor:** [Directive remaining integration gaps](DIRECTIVE_REMAINING_GAPS.md)

## Executive summary

Sonder alpha 9.4 implements the host capabilities Directive previously needed:
post-Director validation and bounded correction, a structured player-safe
people projection, and atomic campaign initialization. There is no remaining
platform blocker among those three contracts.

This report requests two follow-up hardening improvements:

1. Base all people joins and anonymous continuity on immutable person IDs,
   rather than canonical or display names.
2. Add an executable full-pipeline test proving both successful Director
   correction and fail-closed rejection after an unsuccessful correction.

These have different practical weight. Immutable identity handling protects
uncommon but legitimate identity cases and can initially go unused in a
curated Directive campaign. The validator test does not add a missing runtime
feature: Sonder already contains the correction path. It supplies end-to-end
proof for a path Directive is likely to exercise whenever a model proposes an
invalid campaign result.

Neither item should delay a Directive prototype or initial integration.

---

## 1. Immutable identity throughout the people projection

### Current capability

`player_view["people"]` now gives Directive a player-safe structured roster.
Recognized characters expose stable character IDs, viewer-safe names, identity
status, and allowlisted public facts. Unrecognized people expose anonymous
labels and opaque body keys without leaking their canonical identities.

This is sufficient for a normal Directive crew whose members have unique names
and established identities. Directive can key its own ranks, assignments,
duties, and campaign-specific state to the recognized Sonder character ID.

### Remaining weakness

The projection still performs part of its recognized-person join through a
name-keyed roster, and anonymous body continuity is derived from a canonical
name hash. Names are labels, not identities. They can collide or change while
the underlying person remains the same.

The ordinary commissioned-crew case may never expose this weakness. The
following legitimate story cases can:

#### Two people share the same name

Two unrelated characters may naturally have the same name. Genre fiction also
creates less ordinary examples: a transporter accident may produce two
distinct people with the same canonical name, appearance, and history at the
moment of duplication.

A dictionary keyed by name can collapse those two people into one entry or
associate the viewer-safe record with the wrong character ID and public facts.
The UI then cannot reliably represent, select, assign, or track both people.

#### An unidentified person recurs across encounters

The player may encounter an unknown person, lose sight of them, and meet them
again later. The player should be able to recognize continuity such as “the
same injured stranger from Engineering” without learning the person's hidden
canonical identity.

If the anonymous key depends on a name rather than an immutable person ID,
continuity is an incidental consequence of the current label rather than a
property of the person.

#### A person uses an alias or is renamed

A character may initially be known by an alias, later reveal another name, or
receive a corrected or changed name. The player-facing `display_name` should
change as knowledge changes, while the underlying person ID and UI continuity
remain stable.

For an unidentified body, changing the canonical name used to create its hash
can produce a new opaque key. The interface may then treat one continuing
person as two unrelated entries.

### Requested hardening

Use an immutable host-owned person or presence ID as the sole identity key at
every stage of the people projection:

- Join recognized identities to roster records by immutable person ID.
- Derive viewer-safe anonymous IDs from immutable person ID plus any required
  viewer or story namespace, never from a name.
- Treat `display_name`, canonical name, alias, and anonymous label as mutable
  projections attached to that identity.
- Permit two people with identical names to coexist without collision.
- Preserve the same player-safe ID when the viewer's label for a person
  changes, unless Sonder intentionally models the observation as a different
  presence.
- Do not expose the canonical immutable ID for an unidentified person if doing
  so would create a cross-viewer or information leak. A stable viewer-scoped
  opaque derivative is sufficient.

The desired relationship is:

```text
immutable person ID
        |
        +-- recognized viewer-safe ID
        +-- viewer-scoped anonymous ID
        +-- current display name or anonymous label
        +-- aliases and identity knowledge
```

Names describe what a viewer calls someone. They never determine who that
someone is.

### Acceptance tests

- Two characters have the same display and canonical name. Both appear as
  distinct people with different stable IDs and correct individual facts.
- A transporter duplicate initially shares the source character's name but
  remains separately selectable and trackable.
- An unidentified person is observed in two separated encounters. The
  player-safe projection uses the same opaque ID in both encounters when
  Sonder's perception model establishes that they are the same person.
- The unidentified person's canonical name changes between encounters. Their
  viewer-safe opaque ID does not change.
- A recognized character adopts an alias. `display_name` changes for the
  relevant viewer while `id` remains unchanged.
- One viewer recognizes the person and another does not. Each receives an
  appropriate viewer-safe projection without the anonymous projection leaking
  the canonical identity.
- No private name, canonical ID, alias history, or cross-viewer correlation key
  is exposed merely to preserve continuity.

### Directive priority

**Non-blocking robustness improvement.** A curated Directive crew with unique
names can use the current implementation safely in ordinary play. This becomes
important when Directive supports persistent unidentified NPCs, aliases,
identity reveals, duplicate names, or deliberate identity-duplication stories.

---

## 2. Executable full-pipeline Director correction proof

### Current capability

Sonder already implements the runtime path this test would exercise.

An extension registers a deterministic validator with
`api.on_director_result`. The validator receives a read-only `DirectorResult`
after Sonder has merged the result and applied its own deterministic floors.
It accepts the proposal by returning `None`, or refuses it by returning one or
more structured `api.correction` values.

When a validator refuses the first proposal, Sonder:

1. records attributed campaign violations;
2. adds those violations and a correction instruction to the next Director
   request;
3. reruns the complete Director resolution once;
4. reapplies player-authority, movement, passability, reconciliation, and other
   deterministic floors;
5. reruns the extension validators over the corrected result; and
6. either continues with a valid result or follows the validator's error
   policy when violations survive.

The retry is deliberately bounded to one correction attempt. A validator
registered with `on_error="fail"` causes a surviving violation or validator
failure to raise `CampaignInvariantError`, preventing that invalid proposal
from completing as a successful turn. A validator registered with
`on_error="warn"` records the surviving problem but permits continuation.

The runtime flow is therefore already:

```text
Director proposes result
        |
Sonder deterministic floors
        |
Directive validator
        |
        +-- valid ------------------------------> continue toward commit
        |
        +-- invalid
              |
       one attributed correction request
              |
       complete Director resolution reruns
              |
       floors and validator run again
              |
              +-- valid ------------------------> continue toward commit
              |
              +-- invalid + fail policy --------> abort without partial commit
```

Directive is likely to use this path in real play. Models can occasionally
invent a player action, move someone through an inaccessible route, bypass an
assignment, reveal knowledge prematurely, or propose a state transition that
contradicts a deterministic campaign invariant. Directive will register its
essential rules with `on_error="fail"` so an uncorrected violation cannot
become canonical merely because an extension or model misbehaved.

### What current tests establish

Sonder's current tests cover the constituent contracts, including validator
registration, structured correction values, stable validator ordering,
read-only result access, warning and failure policies, exception handling, and
wiring into Director resolution.

That is strong component-level evidence. It does not yet execute the entire
two-response behavior as one test using controlled Director outputs.

### Requested hardening

Add an executable integration test around the actual Director resolution
pipeline. The test must supply deterministic model responses and observe the
real retry boundary rather than duplicate the algorithm in test code or merely
inspect the source for expected calls.

At minimum, prove two scenarios.

#### Successful correction

1. Arrange a campaign invariant, such as a sealed room that the player cannot
   enter.
2. Make the first mocked Director response violate it by moving the player into
   that room.
3. Assert that the registered validator receives the final settled first
   result and returns a structured correction.
4. Assert that Sonder makes exactly one additional Director call.
5. Assert that the second request contains the attributed violation code,
   message, and bounded evidence or correction note.
6. Make the second response comply with the invariant.
7. Assert that Sonder's deterministic floors and the validator run again.
8. Assert that only the corrected result reaches commit and canonical state.
9. Assert that no partial state from the rejected proposal survives.

#### Unsuccessful correction with fail-closed policy

1. Register the same invariant with `on_error="fail"`.
2. Make both the first and second mocked Director responses violate it.
3. Assert that Sonder makes exactly two Director calls total, proving the retry
   is bounded.
4. Assert that the second result is validated and still rejected.
5. Assert that `CampaignInvariantError` or the supported public failure result
   is produced.
6. Assert that no core state, extension state, event, position change, or other
   part of either proposed result is committed.
7. Assert that diagnostics identify the extension and stable violation code.

### Additional useful assertions

- A valid first response performs no second model call.
- Two extensions' violations appear in deterministic order in the correction
  request.
- A validator exception registered as `warn` records a warning without being
  mistaken for a signature mismatch or called twice.
- A validator exception registered as `fail` cannot allow the beat to commit.
- Reroll and variant entry points use the same validation contract if Sonder
  documents them as supported resolution paths.

### Why this belongs at the pipeline level

Unit tests can prove that a validator returns a correction and that a helper
formats correction notes. They cannot independently prove that the production
pipeline:

- places validation after all engine-owned floors;
- sends the correction into the actual second Director request;
- reruns the whole resolution instead of patching the first result;
- reapplies every floor and validator;
- stops after one correction attempt; and
- rolls back all proposed state when fail-closed validation still refuses the
  corrected result.

Those are properties of orchestration and transaction boundaries. Exercising
the real pipeline is the most direct proof.

This test may live in Sonder's suite or in Directive's integration suite. A
Sonder-owned test is preferable because every extension using
`on_director_result` benefits from the guarantee, but no new public API is
required to write it.

### Directive priority

**Strongly recommended proof, not a missing feature or adoption blocker.** The
runtime implementation is present. Directive can begin integration now and can
write this test itself if Sonder does not. The proof should exist before
Directive treats fail-closed result validation as production-grade protection
for campaign invariants.

---

## Requested outcome

| Item | Runtime capability today | Blocks Directive prototype? | Recommended owner |
|---|---|---:|---|
| Immutable people identity | Works for normal unique-name recognized crew; edge cases remain | No | Sonder |
| Full-pipeline correction test | Correction and fail-closed runtime path already exists | No | Prefer Sonder; Directive can supply integration proof |

## Decision in one sentence

Sonder has closed Directive's platform gaps; immutable identity keys would make
the people projection reliable under unusual identity stories, while a real
two-response integration test would prove that the already-implemented
correction path succeeds safely and fails closed without committing a bad beat.
