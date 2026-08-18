# Directive on Sonder — remaining integration gaps

> *Received as-is from Directive's author and kept verbatim, because it is
> evidence. Of its three contracts, §2 — the structured player-safe people
> projection — is built as `player_view["people"]` (schema 2, `story_view.py`;
> `tests/test_story_view.py::TestPeople`). §1 and §3 are registered in
> [`../UNBUILT.md`](../UNBUILT.md) §6.2.*

**Audience:** Sonder Engine maintainer  
**Purpose:** define the three residual host contracts needed for a robust
Directive integration  
**Reviewed against:** Sonder alpha 9.3 (`0b8276aa`), 2026-08-18  
**Predecessor:** [Directive integration gap report](DIRECTIVE_GAP_REPORT.md)

## Executive summary

Sonder alpha 9.3 substantially answered the original Directive gap report. It
now supplies Director context, canonical and player-safe story views, atomic
campaign provisioning, enforced player-authority modes, and a working reference
campaign. Those changes make a real Directive adapter practical.

This report does **not** reopen those completed items. It identifies three
smaller gaps exposed by reviewing how the new capabilities compose:

1. Director context can advise a decision, but an extension cannot validate the
   resulting decision and request a bounded correction before commit.
2. `player_view` protects secrets, but it does not provide a structured,
   stable-id projection suitable for a persistent crew or people interface.
3. `provision_story` is atomic, but campaign-critical context installed
   immediately after it is not part of the same transaction.

The common theme is **closing the last space between “the extension can ask” and
“the host guarantees the resulting campaign remains coherent.”** None requires
Sonder to understand Directive-specific concepts such as starships, ranks,
missions, or Command Bearing.

---

## 1. Deterministic Director-result validation and correction

### What alpha 9.3 already provides

An extension can place attributed, phase-specific context in front of the
Director through `api.director_context(chat_id)` and can dynamically alter a
Director payload through `api.on_director_payload`.

That closes the original context-injection gap. Campaign rules now reach the
decision instead of being appended to narration after the decision was made.

### Remaining limitation

Director context is model input. It can strongly guide a result, but it cannot
guarantee that the result obeys a campaign invariant.

For example, Directive may state that:

- a sealed deck cannot be entered while its pressure door is locked;
- an objective cannot complete until required evidence has been accepted;
- a command cannot take effect while the system carrying it is disabled; or
- an authored fact cannot become known before a legitimate discovery route has
  delivered it.

If the Director disregards that context, Sonder may commit a canonical world
change that contradicts the campaign. A strict extension commit domain can
raise and roll the transaction back, but that loses the beat and gives the
Director no supported opportunity to correct its result.

The reference campaign proves that its sealed-door rule reaches the Director.
It does not prove that an invalid door-opening result is rejected and repaired
before commit.

### Required capability

Provide a supported extension validation seam after Director resolution and
before canonical commit. A validator should be able to:

1. inspect the final interpreted declaration and proposed resolution;
2. inspect the extension's own state and supported canonical story view;
3. accept the result; or
4. return structured violations that trigger one bounded Director correction.

One possible API shape is:

```python
@api.on_director_result
def validate_campaign_result(result, info):
    if violates_mission_invariant(result, info):
        return api.correction(
            code="sealed-location",
            message="Deck 4 remains sealed; no committed movement may enter it.",
            evidence={"room_id": "deck-4", "objective": "restore-pressure"},
        )
    return None
```

The exact names are not important. The contract is.

### Recommended execution model

```text
Director proposes result
        ↓
Sonder deterministic floors validate
        ↓
Extension result validators run in stable order
        ↓
No violations ───────────────→ commit
        ↓ violations
One correction attempt with attributed notes
        ↓
Sonder floors + extension validators run again
        ↓
Valid → commit     Still invalid → fail the beat without partial state
```

The hook should run on the complete, merged Director result—not on an early
prose-author fragment and not once per specialist.

### Safeguards

- Validators are deterministic code; they do not receive a model-call handle.
- Validators cannot directly mutate the Director result.
- A violation has a stable code, bounded message, and optional serializable
  evidence.
- Ordering is deterministic by extension id and validator name.
- At most one host-owned correction attempt occurs per resolution.
- The correction is attributed to the extension in diagnostics and the turn
  trace.
- The corrected result passes Sonder's own deterministic floors again.
- A validator exception follows its declared `warn` or `fail` policy.
- Disabling the extension removes its validators immediately.
- Rerolls and variants use the same validation contract.

### Why a commit-domain rollback is not equivalent

A commit domain answers, “may this transaction finish?” A result validator
answers, “is this a valid proposal, and can the Director repair it?”

Using rollback as the normal campaign-rule mechanism produces a failed turn
where a corrected turn was possible. It also places the explanation after the
expensive pipeline has finished rather than in the retry the Director already
understands.

Commit-domain rollback should remain the final safety net. It should not be the
only supported way to enforce a campaign invariant.

### Acceptance tests

- A standing context says a room is sealed; the first Director result moves the
  player into it; the validator requests correction; the corrected result keeps
  the player outside; only the corrected result commits.
- The first result is valid; no correction call is made.
- The corrected result remains invalid; the complete turn fails and no core or
  extension state is committed.
- Two extensions return violations; their correction notes are ordered and
  attributed deterministically.
- A validator raises under `on_error="warn"`; the warning is recorded and the
  turn may continue.
- A validator raises under `on_error="fail"`; the beat commits nothing.
- Rerolling the Director result invokes the same validation contract.
- Disabling an extension removes its validator before the next beat.

### Directive completion criterion

Directive can express a deterministic mission invariant without importing
Sonder internals. A deliberately noncompliant Director result cannot become
canonical world state, and a compliant correction can complete the beat without
forcing the player to resend their action.

---

## 2. Structured player-safe people projection

### What alpha 9.3 already provides

`api.player_view(chat_id, viewer)` is a genuine information boundary. It is
built from perception already delivered to that viewer, their known identities,
their own location, and—where the viewer is a character—their own relationships
and memories. Unknown information is omitted rather than guessed.

That is the right authority. Directive should not recreate Sonder's admission,
identity, perception, or secrecy rules.

### Remaining limitation

The current projection is strongest as a description of what one viewer has
experienced. It is not yet a structured people directory suitable for a
persistent player interface.

Directive's Crew view needs to render stable entries over many turns. For each
person the player is allowed to identify, it may need:

- a stable character or presence id;
- the name or label the player currently knows;
- whether that identity is recognized, provisional, or merely observed;
- player-known public facts such as role, rank, assignment, visible species,
  or appearance;
- player-visible relationship or operational summaries;
- source/provenance for facts whose display depends on how they were learned.

Today `player_view["knows"]` is a list of names. It does not connect those names
to stable character ids or expose a structured allowlist of player-known public
facts. `api.viewers(chat_id)` has stable ids, but it lists every projectable
mind and is not itself documented as a player-safe roster. Joining those two
answers inside Directive would recreate identity and disclosure logic outside
Sonder.

### Required capability

Extend the player-safe facade with a structured entity projection. This could
be part of `player_view`:

```python
view = api.player_view(chat_id, "player")

view["people"] == [
    {
        "id": "character:17",
        "kind": "character",
        "display_name": "Lt. Reyes",
        "identity_status": "recognized",
        "facts": {
            "role": "chief engineer",
            "rank": "lieutenant",
            "appearance": "wearing a gold operations uniform",
        },
        "fact_sources": {
            "role": "authored_public",
            "rank": "what_i_was_told",
            "appearance": "what_i_experienced",
        },
    }
]
```

or a separate facade:

```python
people = api.player_people(chat_id, viewer="player")
```

The schema should expose only fields Sonder can affirm for that viewer. It
should not attempt to define a universal RPG character sheet.

### Field model

The minimum useful contract is:

| Field | Requirement |
|---|---|
| `id` | Stable across display-name changes and suitable as a UI key |
| `kind` | Player, character, or supported presence type |
| `display_name` | The viewer-safe known name or current anonymous label |
| `identity_status` | Whether the viewer recognizes the person |
| `facts` | Allowlisted player-known public or observed facts only |
| `fact_sources` | Provenance per fact where Sonder has it |
| `last_observed_turn` | Optional; omitted when Sonder cannot answer |

All other fields should be absent.

Directive-specific state—departmental assignment, cohesion, Command Bearing,
mission tasking—can remain in Directive's own namespace and join to the Sonder
id. Sonder only needs to supply the safe identity and fact foundation.

### Safeguards

- Stable ids never depend on display names.
- A hidden canonical name cannot leak through an anonymous label.
- Unknown facts are absent, not `null`, empty defaults, or model deductions.
- The projection reuses Sonder's existing identity and perception ledgers; it
  does not implement a second admission classifier.
- Public authored facts are explicitly allowlisted by schema.
- Private history, psychology, internal goals, undisclosed relationships, and
  other minds' memories are never included.
- Provisional facts are either omitted or clearly marked; the behavior is
  documented and tested.
- One response represents one committed revision.

### Acceptance tests

- A known crew member appears with a stable id and player-known public role.
- Renaming that character changes `display_name` but not `id`.
- An unidentified stranger appears under a safe label without leaking their
  canonical name.
- A character the player has neither encountered nor learned about is absent.
- A secret role stored in private history is absent until the existing engine
  delivers it to the player through a valid route.
- Two viewers receive different facts for the same stable person id.
- Missing rank, species, role, or appearance fields remain absent.
- No private psychology, memory, goal, or hidden relationship field can be
  reached through serialization of the projection.

### Directive completion criterion

The Directive Crew UI can key people by stable Sonder ids and render every
host-owned identity or public-fact field directly from a player-safe API. It
does not join canonical cast data to known-name strings or maintain a parallel
knowledge allowlist.

---

## 3. Transactional campaign initialization

### What alpha 9.3 already provides

`api.provision_story` atomically imports a complete Sonder chat archive, seeds
the extension's namespaced state, records package provenance, and selects the
campaign's player-authority mode. A failure during those operations leaves no
partial story.

This is the correct base and should remain the single scenario importer.

### Remaining limitation

A playable campaign may also require extension-owned runtime configuration from
turn zero, including:

- Director context;
- narration context;
- frame-scoped campaign state;
- initial extension documents; or
- other supported extension-owned records required before the first beat.

The reference campaign provisions the story and then calls `_install_rules` to
set Director context. Those are two writes. If the second operation fails, the
story remains visible and playable with its campaign state and `actor_only`
mode, but without the rule that makes its sealed wing valid.

The problem is not normally a race between two requests. It is failure
atomicity: pressing Start should produce either a complete campaign or no
campaign.

### Required capability

Allow campaign-owned initialization to participate in the same transaction as
`provision_story`, without exposing the database transaction or engine-private
write functions.

There are two reasonable API shapes.

#### Option A — declarative initial extension data

```python
result = api.provision_story(
    package,
    state=initial_state,
    frame_state=initial_frame_state,
    player_authority="actor_only",
    director_context={
        "interpret": SEALED_INTERPRET,
        "resolve": SEALED_RESOLVE,
    },
    narration_context=OPENING_CONTEXT,
    documents={"missions/episode-1": mission_document},
)
```

This is easiest to validate and keeps provisioning data-shaped.

#### Option B — scoped transactional initializer

```python
def initialize_campaign(init):
    init.state.set(initial_state)
    init.frame_state.set(initial_frame_state)
    init.director_context.set(resolve=SEALED_RESOLVE)
    init.documents.put("missions/episode-1", mission_document)

result = api.provision_story(
    package,
    player_authority="actor_only",
    initialize=initialize_campaign,
)
```

The callback receives only handles for the newly created story and supported
extension-owned stores. It is not a general transaction escape hatch.

### Recommendation

Prefer **Option A** for the first contract. It covers known campaign bootstrap
needs, is serializable and lintable, and cannot run arbitrary side effects
inside a database transaction.

Add the callback form only if a real extension demonstrates initialization that
cannot be expressed as data. YAGNI applies here: the purpose is atomic campaign
state, not a general transaction API.

### Safeguards

- Validate all supplied initial values before importing the archive where
  possible.
- Apply every value inside the archive import transaction.
- Allow writes only to the provisioning extension's namespaces.
- Enforce the same size, path, schema, and phase limits as the ordinary APIs.
- Refuse unknown Director phases and invalid authority modes.
- Record package and extension provenance only if all initialization succeeds.
- Do not execute model calls, network calls, UI events, or arbitrary host
  lifecycle actions inside the transaction.
- Return the story id only after the transaction commits.

### Acceptance tests

- Provisioning with Director and narration context succeeds; both are present
  before the first Director or narrator call.
- Invalid Director context fails before a story becomes visible.
- A document write failure rolls back the story, cast, world, extension state,
  authority mode, provenance, and every earlier document/context write.
- An oversized or unserializable value produces an actionable extension error.
- Initial frame-scoped state is associated with the imported active frame.
- Exporting immediately after provisioning contains all initialized campaign
  state and context.
- Branching or checkpointing the new story preserves the complete bootstrap.

### Directive completion criterion

Directive can start a campaign through one supported call. When the call
returns, every host and extension invariant required for turn zero is present.
When any part fails, no partial campaign appears in the player's story list.

---

## 4. Suggested implementation order

1. **Director-result validation.** This protects canonical world state and is
   the only item whose absence can corrupt a campaign during an ordinary beat.
2. **Transactional initialization.** This makes campaign creation reliably
   all-or-nothing and gives the reference campaign a complete turn-zero proof.
3. **Structured people projection.** Its exact fact vocabulary will benefit
   from a small Directive adapter spike showing which host-owned crew fields
   the LCARS interface actually consumes.

The first two are backend integrity contracts. The third is a safe structured
read contract. They can be developed independently once their schemas are
agreed.

---

## 5. Completion checklist

- [ ] An extension can validate the merged Director result before commit.
- [ ] A violation can request one attributed, bounded correction attempt.
- [ ] A still-invalid result cannot commit partial core or extension state.
- [ ] Validation applies equally to normal resolution, correction, reroll, and
      variant paths.
- [ ] A player-safe people projection connects known identities to stable ids.
- [ ] The projection exposes only allowlisted, viewer-known facts.
- [ ] Unknown, secret, and private-mind data is absent.
- [ ] One provisioning call can initialize all campaign-critical context and
      supported extension-owned stores.
- [ ] Any initialization failure leaves no visible story or residual state.
- [ ] The campaign reference extension demonstrates all three contracts.
- [ ] Public documentation and public-contract tests cover every new surface.

---

## 6. Explicit non-goals

This report does not request:

- a Directive-specific mission or starship subsystem in Sonder;
- arbitrary extension mutation of core Director results;
- a second scenario or archive format;
- access to hidden character psychology or unrestricted minds;
- a replacement narrator or prose-author registry;
- a general database transaction handle;
- a universal RPG character-sheet schema; or
- reopening any alpha 9.3 capability already accepted as complete.

## Decision in one sentence

Sonder can now host a Directive campaign prototype; these three contracts make
that integration **enforceable during play, structurally safe to render, and
atomic from its first turn**.
