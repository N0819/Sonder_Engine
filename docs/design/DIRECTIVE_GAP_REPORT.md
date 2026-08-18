# Directive on Sonder — integration gap report

> *Received as-is from Directive's author and kept verbatim, because it is
> evidence. The response — what was built, and the two premises the report got
> wrong — is [`DIRECTIVE_HOST_SURFACE.md`](DIRECTIVE_HOST_SURFACE.md) §9. All
> five gaps in §3 are now built.*

**Audience:** Sonder Engine maintainer  
**Purpose:** identify the smallest Sonder capabilities needed to host Directive well  
**Reviewed against:** Sonder alpha 9.2 (`03f5da66`), 2026-08-17  
**Directive reference:** `0.1.0-pre-alpha.1`

## Executive summary

Directive should not be copied wholesale into Sonder. The useful migration is
replacement-first: Sonder should remain the engine for world state, time,
characters, relationships, memory, spatial simulation, model access, narration,
turn commits, checkpoints, branches, and extension lifecycle. Directive should
become a campaign/gameplay layer that supplies authored missions, deterministic
mission rules, player-safe campaign views, and its LCARS interface.

Sonder already provides most of the host platform this requires. Its extension
system can install and update an extension, run Python stages and commit domains,
persist namespaced state, call models, add routes, inject narrator context, and
mount a substantial browser application through views, top-bar buttons, composer
controls, CSS, and ES modules.

The remaining problem is not general extensibility. It is that a Directive-class
campaign needs a few authoritative seams that are either absent or too narrow.
There are **five essential gaps**:

1. campaign context cannot participate in Director interpretation and resolution;
2. extensions lack a stable, supported read-only view of canonical story state;
3. there is no supported way to provision a complete campaign into a story;
4. there is no host-produced player-safe projection of that state; and
5. Sonder declares player-authority modes but does not enforce them.

Closing those five gaps would make a credible Directive-on-Sonder vertical slice
possible without rebuilding Sonder inside Directive or depending on private
engine internals.

---

## 1. The intended ownership boundary

The goal is not parity between two engines. Each system should own the work it
is best placed to do.

### Sonder should own

- story and branch identity;
- the canonical world clock and frame;
- scenes, rooms, portals, positions, and movement;
- people, minds, relationships, memories, knowledge, and perception boundaries;
- background life and world simulation;
- provider configuration, model calls, structured output, and retries;
- Director interpretation and resolution;
- narration and narration variants;
- transactional commits, checkpoints, archives, and branch inheritance;
- extension installation, trust, enable/disable, updates, and isolation.

Directive should consume those systems instead of maintaining competing copies.

### Directive should own

- campaign packages and scenario-specific authored content;
- mission state machines and deterministic eligibility rules;
- Fair Discovery and duty-report planning where authored facts require a valid
  route into play;
- Directive-specific gameplay concepts such as ship state, departmental
  readiness, crew cohesion, Command Bearing, and episode objectives;
- the player-facing LCARS experience;
- campaign-specific summaries and explanations derived from canonical Sonder
  state.

Some Directive concepts may later prove generally useful to Sonder. That is a
separate adoption decision. The host contract should not require Sonder to
become Starfleet-specific.

---

## 2. What Sonder already supplies

The following are foundations Directive can use now. They are not migration
gaps.

| Need | Existing Sonder support | Directive use |
|---|---|---|
| Extension lifecycle | Install, update, enable, disable, remove, safe mode, per-item load isolation | Ship Directive as a normal extension |
| Backend execution | Python stages, hooks, specialists, and commit domains | Run mission planning and commit campaign state |
| Transactional extension state | Namespaced story and character state; commit participation | Store Directive-owned campaign state without a second database |
| Model access | Extension text and structured-output calls | Run campaign-specific classifiers or planners when deterministic logic is insufficient |
| Narrator guidance | Standing attributed narration context and payload hook | Put current mission guidance in front of the narrator |
| HTTP surface | Namespaced extension routes | Serve campaign data and actions to the Directive UI |
| Application UI | Registered views, top-bar buttons, composer controls, CSS, and ES-module assets | Host the LCARS shell without patching Sonder's DOM |
| Story continuity | Checkpoint, archive, and branch handling carries extension state | Keep campaign state aligned with Sonder story history |

This is a much stronger base than a simple chat frontend. Directive should not
rebuild these systems.

---

## 3. Essential gaps

These are the capabilities Directive needs absolutely. Each request is written
as a general Sonder extension feature rather than a Directive-only special case.

### Gap 1 — Director context injection

**Current limitation**

An extension can add context to narration, after the Director has already
interpreted and resolved the player's action. That is sufficient for prose
styling and reader-visible mission reminders, but too late for campaign rules
that must affect what the engine believes the action means or which outcome is
valid.

Examples include an objective becoming eligible only after required evidence,
a command being invalid while a system is disabled, or an authored fact being
unavailable until a legitimate discovery route has completed.

**Requested Sonder capability**

Provide an attributed, bounded extension context seam for both Director phases:

- interpretation;
- resolution.

This could resemble the existing narration API:

```python
api.director_context(chat_id).set({
    "interpret": "...",
    "resolve": "...",
})
```

or payload hooks with equivalent coverage:

```python
api.on_director_interpret_payload(handler)
api.on_director_resolve_payload(handler)
```

The exact spelling is unimportant. The important contract is that the extension
can contribute an identified context block before each decision, without
replacing the Director or reading private state through an unsupported object.

**Required safeguards**

- attribute every contribution to the extension id;
- impose an explicit size budget;
- preserve deterministic ordering between extensions;
- remove contributions immediately when an extension is disabled;
- expose the applied contribution in diagnostics;
- do not allow an extension to impersonate engine-owned instructions.

**Acceptance test**

An extension installs a mission constraint. The same player message resolves
differently with the extension enabled and disabled; the narrator receives the
committed result, and the trace identifies the extension context that influenced
the Director.

### Gap 2 — Stable read-only canonical story view

**Current limitation**

Extension stages receive carefully bounded turn data, and commit hooks can see
the result of the current turn. That containment is valuable. However, a
campaign layer also needs to derive mission eligibility and render its UI from
the settled story state. Reaching into engine modules or the database directly
would make the integration fragile and defeat the extension boundary.

**Requested Sonder capability**

Provide a versioned, read-only facade for canonical state, available from
extension routes and, where appropriate, from the transactional `CommitView`.
The minimum useful view is:

- story id, branch id, turn id, and turn index;
- canonical clock and current frame;
- active scene and known locations;
- current positions of relevant entities;
- stable character ids and player-visible identity data;
- relationships and knowledge filtered for an identified viewer;
- recent committed events and their stable ids;
- provenance sufficient to tell authored, observed, inferred, and provisional
  facts apart.

The facade does not need to expose raw tables, arbitrary minds, hidden reasoning,
or mutation handles. It should return ordinary immutable/serialized values with
a documented schema version.

One possible shape is:

```python
snapshot = api.story_view(chat_id, viewer_id=persona_id)
```

**Acceptance test**

A Directive route can render the current stardate, location, visible crew,
relationship status, and mission prerequisites using only public extension APIs.
It does not import engine internals or open the database.

### Gap 3 — Supported campaign provisioning

**Current limitation**

A Directive campaign is more than extension settings. Starting one may require
a story, persona, cast, rooms, portals, authored lore, initial relationships,
clock state, and Directive-owned mission data to agree from the first turn.
There is no supported extension operation for creating that coherent starting
state.

**Requested Sonder capability**

Provide a validated campaign/story provisioning API. It should accept a
declarative package or a sequence of supported builder calls and create the
initial state atomically.

The minimum requirements are:

- create a new story from an extension-provided definition;
- create or bind the player persona;
- create initial characters with stable ids;
- create rooms, portals, positions, and initial scene/frame data;
- import authored public and secret lore through the appropriate firewall;
- initialize clock and relationship state through supported schemas;
- initialize the extension's own namespaced state;
- validate references before committing anything;
- fail atomically, with actionable validation errors;
- record the extension and package version as provenance.

This should be a general scenario-import contract. Directive-specific package
translation can remain inside Directive.

**Acceptance test**

From the Directive view, a player selects a bundled campaign and presses Start.
Sonder creates a playable story with its cast, map, clock, lore, and Directive
mission state. A validation failure leaves no partial story behind.

### Gap 4 — Player-safe projection

**Current limitation**

The LCARS UI must show only what the current player is allowed to know. A broad
canonical snapshot is not safe enough if the extension must rediscover Sonder's
perception, identity, secrecy, and provenance rules on its own. Duplicating that
filter would create two authorities that can drift.

**Requested Sonder capability**

Make the host the authority for viewer-safe data:

```python
view = api.player_view(chat_id, persona_id)
```

The projection should contain only facts currently available to that persona,
using stable ids and source/provenance where useful. Secret fields and unknown
values should be **absent**, not filled with guesses, personality deductions,
or convenient defaults.

The projection may be the viewer-filtered mode of the story facade in Gap 2;
it does not have to be a separate subsystem. It is listed separately because
the safety guarantee is an absolute product requirement.

**Required behavior**

- apply the same information firewall used by Sonder narration and perception;
- distinguish public identity from hidden mind/personality state;
- never infer a missing player fact for display;
- expose stable ids so UI selections remain valid across renames;
- document whether provisional facts are included and how they are marked;
- keep projection results consistent within one committed revision.

**Acceptance test**

Two personas request the same story view and receive different knowledge where
appropriate. A secret known only to one character is absent from the other
view, while shared public facts remain identical.

### Gap 5 — Enforced player authority

**Current limitation**

`PlayerAuthorityMode` exists, but Sonder's own unbuilt register records that it
is not consumed. Directive cannot rely on a prompt asking the model to respect
player agency. The runtime must prevent generated interpretation, resolution,
or narration from inventing player dialogue, decisions, feelings, or actions
that the player did not supply.

**Requested Sonder capability**

Enforce the selected authority mode across the complete generation path, at
least including:

- Director interpretation;
- Director resolution;
- narration;
- retries and fallback paths;
- variant generation;
- any specialist whose output can become player-visible canon.

For Directive, the required strict behavior is equivalent to `actor_only`:
generated output may describe the world reacting to the player's submitted
action, but may not add a new player line, choice, intention, emotion, memory,
or voluntary action.

Enforcement should happen before output becomes committed or accepted canon.
A validator-and-retry mechanism is acceptable; prompt text by itself is not.

**Acceptance test**

Adversarial fixtures cause the model to add player speech, internal emotion,
and an unrequested follow-on action. Each is rejected or repaired before commit,
including through retry, fallback, and variant paths. World and NPC reactions
remain narratable.

---

## 4. Useful improvements that are not blockers

These would improve the long-term developer experience, but Directive can ship
a first Sonder integration without them.

| Improvement | Why it helps | Why it does not block |
|---|---|---|
| Extension-owned model lanes and sampler settings | Gives campaign planners independently configurable inference | Existing extension model calls are sufficient for an initial integration |
| Native extension settings surface | Avoids building configuration inside the Directive view | Directive can own settings in its registered application view |
| Host notification API | Makes campaign alerts consistent with Sonder chrome | Directive can render notifications inside its own view initially |
| Document/blob storage | Better fit for large campaign packages and exports | Bundled assets plus namespaced state and routes can support a first release |
| Prose-author replacement | Could support a total-conversion narrator | Directive only needs to constrain the existing Director/narrator, not replace it |
| Frame-scoped extension state | Helps campaigns spanning eras or timelines | Directive can key its own namespaced data by frame until demand is proven |
| Additional DOM freedom | Allows arbitrary host restyling | Current registered views, controls, modules, and CSS are enough for the LCARS app |
| Directive-owned accepted-pair ledger | Reproduces its SillyTavern settlement model | Sonder's own transaction, checkpoint, and branch model should replace it |

These should not delay the five essential seams.

---

## 5. Minimum viable Directive-on-Sonder flow

The following vertical slice is the practical definition of “the gaps are
closed”:

1. The player installs and enables Directive through Sonder's extension manager.
2. Directive registers a top-bar launcher, a full application view, backend
   routes, stages, and a commit domain.
3. The player chooses a bundled Directive campaign.
4. Directive asks Sonder to provision the story, persona, cast, map, clock,
   lore, and initial campaign state atomically.
5. The LCARS view reads a player-safe canonical snapshot and displays the
   current situation and valid mission information.
6. The player submits an action through Sonder's normal composer.
7. Directive contributes current campaign rules to Director interpretation and
   resolution.
8. Sonder resolves and commits the turn while enforcing strict player authority.
9. Directive's transactional commit domain advances only the mission state whose
   deterministic prerequisites were satisfied.
10. Sonder narrates the committed result with Directive's attributed narration
    context; refreshing, checkpointing, or branching preserves a coherent
    campaign.

If this works without private imports, direct database access, DOM probing, or a
second world model, Sonder is ready to host the core Directive experience.

---

## 6. Suggested implementation order

1. **Enforce player authority.** This is independently valuable to Sonder and
   protects every later integration test from canonizing invented player acts.
2. **Add the read-only/player-safe story facade.** Treat player projection as a
   security boundary of that facade, not as UI convenience.
3. **Add Director context injection.** Reuse the attribution, lifecycle,
   ordering, and diagnostics patterns of narration context.
4. **Add campaign provisioning.** Build it on the same public schemas returned
   by the facade so import and readback can be tested together.
5. **Prove the vertical slice with a tiny reference campaign.** One room change,
   two characters, one secret, one gated objective, and one forbidden invented
   player line are enough to exercise all five contracts.

This order is a recommendation, not a hidden dependency graph. Provisioning can
be developed in parallel with the context and projection work if their schemas
are agreed first.

---

## 7. Completion checklist for the Sonder maintainer

- [ ] An extension can influence Director interpretation and resolution through
      attributed, bounded, documented context.
- [ ] An extension route can read a versioned canonical story snapshot without
      private imports or database access.
- [ ] The snapshot can be filtered authoritatively for a specified player
      persona.
- [ ] Unknown and secret values are omitted from that player view.
- [ ] An extension can atomically provision a complete scenario using supported
      schemas.
- [ ] Provisioning validates cross-references and records package provenance.
- [ ] `PlayerAuthorityMode` is enforced before commit across normal, retry,
      fallback, specialist, and variant paths.
- [ ] Checkpoint, archive, branch, refresh, enable/disable, and extension update
      preserve or retire all new state and context correctly.
- [ ] A reference extension demonstrates the complete vertical slice.
- [ ] Every new surface is documented in the extension guide and covered by
      public-contract tests.

---

## 8. Related Sonder documentation

- [Extension author guide](../guides/EXTENSIONS.md) — the authoritative account
  of the extension surface as built.
- [Hosting a Directive-class extension](DIRECTIVE_HOST_SURFACE.md) — the earlier
  measurement of Directive's host boundary and the UI/narration/module work that
  Sonder has already completed.
- [Unbuilt register](../UNBUILT.md) — authoritative status for accepted but
  unfinished Sonder work, including player-authority enforcement and secondary
  extension improvements.
- [Directive adoption proposal](PROPOSAL_DIRECTIVE_ADOPTIONS.md) — potentially
  reusable Directive ideas; intentionally separate from the hosting gaps in this
  report.

## Decision in one sentence

Sonder is ready to supply most of Directive's foundation; it becomes a suitable
host when extensions can safely **seed a campaign, see the resulting world,
influence Director decisions, project only player-knowable facts, and rely on
runtime-enforced player agency**.
