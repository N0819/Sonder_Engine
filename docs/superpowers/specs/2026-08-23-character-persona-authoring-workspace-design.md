# Character and Persona Authoring Workspace Design

**Status:** Approved for implementation  
**Date:** 2026-08-23  
**Change category:** Design Bible extension  
**Related ledger items:** UI-FU-01, UI-FU-02

## Purpose

Replace the cramped Character and Persona editor inside the contextual Library
pane with one shared, focused authoring workspace. The workspace serves reusable
Characters, reusable Personas, and story-specific Character cards without
creating a second persistence model or weakening the existing lossless document
contract.

The current Design Bible and replacement UI remain authoritative. Earlier
interfaces may identify capabilities, but do not determine composition,
navigation, or visual treatment.

## Goals

- Give long, structured person documents enough width and vertical ownership to
  be understandable and usable.
- Use one authoring framework for reusable Characters, Personas, and
  story-specific Character cards.
- Preserve every maintained field and workflow documented in the capability
  audit.
- Keep save authority explicit: browser-local drafts are recoverable, while
  server documents change only after accepted Save.
- Return to the same Library category, scope, query, sort, visibility,
  selection, and scroll position.
- Provide the same capability on desktop, tablet, phone, and short landscape.

## Non-goals

- Redesigning the Library ledger or global application shell.
- Changing Character or Persona schemas, server routes, revision rules, or
  Story membership semantics.
- Adding autosave to server-owned person documents.
- Building a WYSIWYG card designer, arbitrary schema designer, or theme editor.
- Giving legacy layouts visual or information-architecture authority.

## Approaches considered

### 1. Library workspace takeover — selected

The global navigation remains in place. While a person authoring route is
active, the Library's category rail, material ledger, and contextual inspector
yield their inner space to a dedicated authoring workspace. Back restores the
retained Library route and presentation state.

This gives the editor useful width, creates one responsive model, and preserves
Library as the predictable home for authoring.

### 2. Expanded contextual inspector — rejected

Keeping the editor in the inspector would preserve the existing mount point,
but leaves long forms competing with the ledger and creates different desktop
and compact interaction models. It does not resolve the original density
problem.

### 3. Modal or overlay editor — rejected

A modal would make the editor visually focused, but long forms, generation,
validation, Quick Start, and mobile keyboards exceed a decision dialog's
contract. It would also complicate history and focus restoration.

## Workspace contract

### Entry

- Edit from Character or Persona detail opens the shared workspace with the
  selected item and `mode=edit`.
- Edit Story card opens the same workspace with `mode=story-card` and the
  selected Story association.
- New Character and New Persona open the same workspace with `mode=create`.
- Character and Persona import use the same outer workspace with `mode=import`.
- Route navigation clears transient inspector layers before the workspace is
  presented.

### Outer geometry

- The global Play, Library, and Settings navigation remains visible.
- The Library inner workspace owns the available destination width and height.
- The contextual inspector and its toggle are suppressed only while person
  authoring is active; the user's persisted inspector state is not changed.
- The workspace has a stable header, section navigation, one scrollable editor
  body, and a sticky action area when Save is available.
- Story and Lore authoring retain their current presentation in this change.

### Header

The persistent header contains:

1. Back to Library;
2. item type and, for a story card, Story context;
3. editable document name or a clear new-item title;
4. save state;
5. the primary Save action and a restrained More/secondary cluster where
   needed.

Save state uses distinct language:

- `Saved to Library` — server document and draft agree;
- `Draft saved on this device` — local recoverable draft differs;
- `Saving…` — an owned request is active;
- conflict/failure — work remains locally recoverable and the message names the
  next action.

### Sections

The workspace exposes a small section navigator. It changes which editor
section is visible without changing routes or server state.

Shared sections:

- **Basics:** name, aliases, pronouns, stable identity disclosure.
- **Appearance:** visible appearance, outfit, senses, embodiment, and abilities.
- **History:** public and private authored history.
- **Advanced:** the complete JSON document with explicit Apply; invalid JSON
  changes nothing.

Character sections:

- **Inner life:** psychology, values, coping, stress profile, drives, social
  voice, and initial state.
- **Opening:** first message, stored greetings, generation/recovery tools, and
  other opening fields.
- **Simulation:** tier, temperature, curiosity, sampler, and off-screen opt-in.
- **Quick Start:** Persona, greeting, Lore, knowledge relationship, and lived
  location. This appears only where the maintained Quick Start contract is
  available.

Persona section:

- **Story presence:** narration voice and other Persona-specific story-facing
  fields.

Unknown or extension-owned top-level fields remain reachable in an **Additional
fields** section and in Advanced. The editor never drops a field merely because
it lacks a bespoke control.

### Field behavior

- Plain labels remain visible; placeholders never replace labels.
- Long prose uses textareas and stages a local draft on input.
- Structured arrays retain the current lossless JSON control until a dedicated
  typed control is separately specified.
- Invalid structured JSON is marked at the field and is not staged.
- Stable identity is read-only.
- Save validates required fields, reveals the affected section, focuses the
  first invalid control, and retains every other staged value.
- Generation operates on the current draft, presents a reversible preview, and
  never writes before Save.

## Navigation and draft contract

- The current route remains the sole identity of the active document.
- Entering authoring captures the parent Library route implied by removing
  `mode` and workflow-only query keys.
- Back removes the authoring mode without dropping category, scope, Story,
  query, sort, visibility, or selected item.
- The Library records its final scroll offset before unmounting. Returning uses
  that exact parent-route key and restores the offset.
- Leaving with a dirty or invalid draft does not show a destructive modal
  because every accepted field change is already in the bounded owner-scoped
  local draft. The header explains that the draft is local.
- Discard draft is explicit and restores the last accepted server document.
- Create/import workflows return to their originating category after cancel or
  completion.
- A direct authoring link with no usable parent falls back to the selected
  item's ordinary Library route, or to its category for create/import.

## Runtime and data ownership

`library-authoring-runtime.js` remains the only browser authoring authority. It
continues to own:

- owner identity and stale-response rejection;
- local draft envelopes;
- revision tokens and conflict handling;
- load, stage, save, discard, import, preview, duplicate, and Quick Start;
- routing after accepted create/import/duplicate operations.

The new workspace is a presentation adapter. It may own bounded ephemeral
section choice and focus targets, but may not reconstruct server documents,
patch Library associations optimistically, or write engine state directly.

## Responsive behavior

- **Wide/expansive:** section navigation occupies a restrained left column and
  the active form occupies the main reading column.
- **Medium/tablet:** section navigation becomes a compact horizontal strip or
  select while the form keeps a readable measure.
- **Compact/phone:** the workspace becomes a full-screen destination stage;
  Back, title/save state, and Save remain reachable. Fields stack to one column
  and use safe mobile font sizes.
- **Short landscape:** secondary descriptions collapse before controls; the
  header and actions remain usable and the body owns vertical scrolling.
- Every interactive target is at least 44 by 44 CSS pixels. No maintained
  capability depends on hover.

## Accessibility and localization

- The workspace is a named main-region subview with one `h1`/primary editor
  heading and ordered section headings.
- Section navigation exposes selected state through semantics, text, and tone.
- Focus moves to the workspace heading on entry and returns to the selected
  Library row on Back when that row exists.
- Status and validation messages use polite live regions; failures do not
  replace the form.
- Keyboard users can move through sections and reach Save without traversing
  hidden controls.
- New interface copy is added to the English and Japanese UI catalogs in the
  same release. User-authored names and prose are never translated.

## Error handling

- Load failure keeps Back available and explains that no edits were applied.
- Save conflict or failure keeps the local draft, section, and scroll position.
- Preview failure restores the pre-preview draft and offers Retry.
- Invalid Advanced or structured JSON remains local to that control and cannot
  overwrite the active draft.
- Quick Start failure stays in the editor with the saved Character and current
  launch choices recoverable.

## Verification

### Behavioral matrix

- Create, edit, save, discard, reload, and recover a local draft for both
  Characters and Personas.
- Edit and save a story-specific Character card without changing live mood,
  memory, relationships, or physical state.
- Exercise generation previews, appearance fill, psychology fill, greeting
  generation/recovery, Quick Start, import, export, and duplicate.
- Prove unknown document fields round-trip unchanged.
- Prove stale revisions reject writes while preserving the draft.
- Prove Back restores route query, selection, and scroll.
- Prove direct links and browser Back/Forward remain coherent.

### Browser matrix

- 1440 × 900 desktop;
- 1024 × 768 tablet/medium;
- 390 × 844 phone portrait;
- 844 × 390 short landscape;
- 200% zoom equivalent;
- keyboard-only and reduced-motion passes.

Each viewport captures Basics, a dense Character section, Advanced validation,
dirty state, and a recoverable failure. Screenshots are compared against the
approved Design Bible composition and recorded with implementation evidence.

## Documentation impact

- Update `docs/guides/INTERFACE.md` with the workspace and draft ownership
  contract in the same implementation commit.
- Record the extension in the Design Bible decision register and changelog.
- Update UI-FU-01 and UI-FU-02 only when their browser criteria pass.
- Retain the capability audit as implementation evidence.

