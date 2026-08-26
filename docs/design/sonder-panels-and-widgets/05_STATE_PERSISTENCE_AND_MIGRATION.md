# 05. State, Persistence, and Migration

## Principle

Panel persistence saves composition. It does not become a second store for
story, Library, Settings, credential, extension, or generation truth.

## Global scope

Panel definitions are global across stories for the same host profile. The
same Panel order and arrangements appear regardless of which story is loaded.

Global scope does not yet imply cross-device synchronization. The persistence
implementation must explicitly choose browser-local, host-profile server
storage, or a synchronized user profile. That choice cannot change the saved
schema's ownership boundaries.

## Saved Panel envelope

A versioned Panel envelope contains only composition and bounded presentation
state:

```json
{
  "schema": "sonder.panels.v1",
  "revision": 12,
  "activePanelId": "panel-scene",
  "panels": [
    {
      "id": "panel-scene",
      "origin": "shipped.scene",
      "name": "Scene",
      "order": 0,
      "template": "story-stage.v1",
      "layout": {},
      "widgets": []
    }
  ]
}
```

The example describes shape, not a committed storage API.

Each Widget instance record contains:

- stable instance identifier;
- stable Widget type identifier;
- Widget schema/configuration version;
- slot, stack, order, span, and floating geometry as applicable;
- harmless persisted presentation configuration;
- no story identifier for active-story Widgets.

## State classification

### Persist globally

- Panel identity, name, order, and shipped origin;
- selected Panel;
- template and exact valid geometry;
- Widget instance identity and placement;
- Widget density, sort, filters, subpanel, and active tab when safe;
- collapsed toolbar/zone state;
- Catalog view mode, favorites, and last category;
- schema and revision identity.

### Persist through existing qualified owners

- composer drafts scoped to story/frame;
- long editor drafts scoped to record or story;
- themes and accessibility preferences;
- mute, volume, and other already-qualified device preferences;
- server-owned Settings values;
- extension-owned settings.

### Session-only

- Catalog search text;
- temporary compatibility filters;
- drag and placement state;
- current hover/focus target;
- transient expanded-browser scroll;
- Undo receipts after expiry;
- loading and request state.

### Never enter Panel persistence

- provider credentials or session secrets;
- story prose, authored sheets, world state, memories, or transcript data;
- model output or technical streams;
- join codes or guest identity material;
- extension private data;
- unsanitized HTML;
- active-story content copied for convenience.

## Active-story switching

The active story is application context, not Panel data. A story switch uses
captured identity and stale-result rejection:

1. invalidate active-story and story-selection projections;
2. preserve Panel and Widget instance identity;
3. clear selections that do not belong to the new story;
4. preserve qualified drafts under their actual prior owner;
5. load every active-story projection against the same new story identity;
6. reject late prior-story results.

A user returning to the prior story may recover its owner-qualified draft. The
Panel layout does not carry or retarget it.

## Save behavior

Layout mutation is atomic. A successful save advances the Panel-envelope
revision. Failed persistence leaves the last confirmed layout authoritative and
keeps the attempted arrangement available for Retry or Revert where practical.

The UI must distinguish:

- saving;
- saved;
- locally changed but not confirmed;
- save failed with arrangement preserved;
- stale because another owner changed the layout.

Automatic retries may repeat safe reads. They do not blindly replay a layout
write over a newer revision.

## Shipped defaults

Each shipped default Panel records a stable `origin` and a versioned current
default definition supplied by the release.

**Reset Panel to Defaults**:

- names the affected Panel;
- shows that user layout changes will be replaced;
- restores the current shipped definition atomically;
- leaves all application data and Settings untouched;
- offers Undo when the prior envelope can be retained safely.

Release updates do not overwrite edited defaults automatically. A new shipped
default version becomes the target only when the user chooses Reset or when a
required migration can preserve their arrangement.

## Migration

Migrations are versioned, ordered, idempotent, and recoverable. They operate on
copied envelopes and commit only after validation.

Migration cases include:

- renamed Widget type with stable alias;
- Widget configuration schema change;
- removed or disabled extension Widget;
- changed minimum dimensions;
- retired layout template;
- current viewport unable to express saved geometry;
- old Scene/Library/Settings route state imported into shipped default Panels.

When an exact migration is impossible, retain a placeholder and the original
configuration payload. Do not silently discard unknown Widget data.

## Missing Widgets

A missing Widget renders a bounded placeholder showing:

- saved Widget name/type when available;
- why it is unavailable;
- whether an extension is missing or disabled;
- Retry, Enable/Install when authorized, Replace, and Remove actions;
- preserved slot geometry.

Reinstalling or re-enabling a compatible definition restores the instance in
place.

## Concurrency

The storage owner must compare Panel revision on write. Conflicting changes do
not merge by guessing at geometry. The user receives the newer confirmed
arrangement and an explicit option to retry their operation when safe.

If cross-device synchronization is later introduced, it must define a real
conflict model before enabling concurrent layout writes.

## Export and sharing boundary

Panel export, import, and sharing are not part of the first approved contract.
If added later, exports must contain only the safe Panel envelope and Widget
configuration. They must omit credentials, story data, drafts, and extension
private state, and must validate every imported Widget against the local
registry.

