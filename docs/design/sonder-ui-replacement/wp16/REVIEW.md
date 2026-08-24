# WP-16 Person Authoring Workspace Review

**Review date:** 2026-08-23  
**Surface:** Reusable Character, reusable Persona, and story-specific Character
card authoring  
**Result:** Accepted

## Contract reviewed

The Library destination owns long-form person authoring. Concise selected item
detail remains contextual outside authoring, while the authoring route
collapses the inspector track without changing the stored inspector preference.
Reusable Characters, reusable Personas, and story-specific Character cards use
one section, validation, draft, and action framework. The story-card URL mode is
now admitted only for a selected Character with a valid Story context; the
existing reusable-versus-story-owned load and save boundaries remain intact.

Ordinary fields are selected by a maintained semantic path registry. It gives
engine concepts plain labels, literal bounds, suitable controls, and concise
help without renaming stored data. Unknown and extension-owned values remain
lossless under Additional fields and Advanced. Peer content sections remain in
the section rail or compact strip; Start a Story, Additional fields, and
Advanced are staged under one More disclosure.

## Browser evidence

The repeatable capture is `tools/capture_ui_person_editor.py`. It loads the real
application module graph, stubs only public API responses, waits for layout
stability, and uses reduced motion. The 13 captured states cover both reusable
document kinds, story-owned editing, destructive and validation states,
localization, Accessibility Mode, and zoom as well as geometry.

| Viewport | Evidence | Review |
|---|---|---|
| 1440×900 | `screenshots/person-editor-1440.png` | Full destination width, restrained section rail, readable document measure, stable actions, no unused inspector track. |
| 1024×768 | `screenshots/person-editor-1024.png` | Equivalent section and document hierarchy at medium width. |
| 1024×600 | `screenshots/person-editor-1024x600.png` | Short-height staging exposes every section through a horizontal strip while preserving one document scroll owner and reachable actions. |
| 390×844 | `screenshots/person-editor-390.png` | Horizontal section staging, single document scroll, persistent Back/save state/actions, no clipped controls. |
| 360×800 | `screenshots/person-editor-360.png` | Narrow-phone strip keeps More anchored while peer sections remain horizontally reachable. |
| 844×390 | `screenshots/person-editor-844x390.png` | Short-landscape staging retains the full section strip and reachable Save while the document body scrolls independently. |
| Persona, 1440×900 | `screenshots/persona-editor-1440.png` | The shared framework presents the shorter Persona section set without empty Character-only areas. |
| Story Character card, 1440×900 | `screenshots/story-character-editor-1440.png` | The maintained route enters the shared workspace, identifies Story ownership, and locks immutable identity. |
| Discard confirmation, 1440×900 | `screenshots/person-editor-discard-1440.png` | The named native modal explains local-draft restoration and separates safe and destructive choices. |
| Invalid Advanced, 1440×900 | `screenshots/person-editor-invalid-1440.png` | The tall structured editor retains invalid text and exposes its error without collapsing. |
| Japanese, 390×844 | `screenshots/person-editor-ja-390.png` | Longer localized section and control labels remain reachable without page overflow. |
| Accessibility Mode, 1440×900 | `screenshots/person-editor-accessibility-1440.png` | Stronger accessibility styling preserves hierarchy, focus signal, and action ownership. |
| 200% zoom equivalent | `screenshots/person-editor-zoom-200.png` | Content reflows to compact staging with one scroll owner and reachable actions. |

The focused geometry test covers all six viewports and asserts one named
vertical document scroll owner, no horizontal page overflow, no unused
inspector track, 44 px visible controls, and no rendered focus targets inside
hidden panels.

## Behavior and keyboard review

- Arrow keys, Home, and End move between semantic section tabs.
- Section selection survives destination rerenders and local-draft re-entry.
- Invalid required or structured fields reveal their section and enclosing
  disclosures before focus moves to the first invalid control.
- Discard opens a named native modal; Escape and Keep editing preserve the
  draft, while the destructive confirmation makes exactly one discard call.
- Back preserves category, scope, Story, query, sort, visibility, selection,
  exact scroll, and device-local draft, then returns focus to the selected row.
- Save state distinguishes `Saved to Library` from `Draft saved on this
  device`; conflict and failure retain the recoverable draft.
- Reduced motion changes no layout or access path and the capture uses the
  reduced-motion browser preference.
- The real Library route retains `mode=story-card` and Story context, loads the
  shared workspace, locks Name, and keeps Story-owned persistence authority.

## Visual comparison

This workspace extends the approved Library replacement rather than revising
it. It retains the existing carbon ground, cyan interaction signal, amber type
kicker, technical typography roles, compact geometry, integrated action
cluster, and three-destination shell. The approved difference is task staging:
long-form authoring replaces the Library body and temporarily suppresses the
contextual inspector. The Library hierarchy and global visual direction are
unchanged. The connected topbar and editor-owned footer make navigation, state,
and document actions read as one workspace without introducing another visual
language.

## Verification

- `browser_tests/test_ui_character_persona_editor.py`
- `browser_tests/test_ui_library_authoring.py`
- `tests/test_ui_character_persona_editor_contracts.py`
- `tests/test_ui_library_authoring_contracts.py`
- `tests/test_library_character_persona_authoring.py`
- `tests/test_ui_runtime_contracts.py`

Verification results on the reviewed candidate:

- focused UI contract and persistence gate: 25 passed;
- focused real-browser editor and Library gate: 27 passed;
- complete browser suite: 219 passed;
- complete repository suite: 8,802 passed and 4 platform-specific skipped;
- catalog extraction: 922 English source messages with a matching Japanese key
  set;
- deterministic visual capture: 13 states completed and reviewed;
- immutable UI release: `alpha98-ui5-7fa758fa6df7`.

`tools/project_check.py` continues to report the seven previously recorded
direct-import findings in the installed Directive extension integration test.
This workspace does not modify that extension boundary.

No open design decision remains for the shared workspace. User-authored themes
remain a separately scoped backlog feature.
