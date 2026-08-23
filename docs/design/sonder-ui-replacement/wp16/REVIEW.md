# WP-16 Person Authoring Workspace Review

**Review date:** 2026-08-23  
**Surface:** Reusable Character, reusable Persona, and story-specific Character
card authoring  
**Result:** Accepted

## Contract reviewed

The Library destination now owns long-form person authoring. Concise selected
item detail remains contextual outside authoring, while the authoring route
collapses the inspector track without changing the stored inspector preference.
All three document types use the same section, validation, draft, and action
framework. The server routes and reusable-versus-story-owned boundaries are
unchanged.

## Browser evidence

The repeatable capture is `tools/capture_ui_person_editor.py`. It loads the real
application module graph, stubs only public API responses, opens a dense
Character document, expands Inner life, waits for layout stability, and uses
reduced motion.

| Viewport | Evidence | Review |
|---|---|---|
| 1440×900 | `screenshots/person-editor-1440.png` | Full destination width, restrained section rail, readable document measure, stable actions, no unused inspector track. |
| 1024×768 | `screenshots/person-editor-1024.png` | Equivalent section and document hierarchy at medium width. |
| 390×844 | `screenshots/person-editor-390.png` | Horizontal section staging, single document scroll, persistent Back/save state/actions, no clipped controls. |
| 844×390 | `screenshots/person-editor-844x390.png` | Short-landscape staging retains the full section strip and reachable Save while the document body scrolls independently. |

The focused geometry test also covers all four viewports and asserts one named
vertical document scroll owner, no horizontal page overflow, no unused
inspector track, 44 px visible controls, and no rendered focus targets inside
hidden panels.

## Behavior and keyboard review

- Arrow keys, Home, and End move between semantic section tabs.
- Section selection survives destination rerenders and local-draft re-entry.
- Invalid required or structured fields reveal their section and enclosing
  disclosures before focus moves to the first invalid control.
- Back preserves category, scope, Story, query, sort, visibility, selection,
  exact scroll, and device-local draft, then returns focus to the selected row.
- Save state distinguishes `Saved to Library` from `Draft saved on this
  device`; conflict and failure retain the recoverable draft.
- Reduced motion changes no layout or access path and the capture uses the
  reduced-motion browser preference.

## Visual comparison

This workspace extends the approved Library replacement rather than revising
it. It retains the existing carbon ground, cyan interaction signal, amber type
kicker, technical typography roles, compact geometry, integrated action
cluster, and three-destination shell. The approved difference is task staging:
long-form authoring replaces the Library body and temporarily suppresses the
contextual inspector. The Library hierarchy and global visual direction are
unchanged.

## Verification

- `browser_tests/test_ui_character_persona_editor.py`
- `browser_tests/test_ui_library_authoring.py`
- `tests/test_ui_character_persona_editor_contracts.py`
- `tests/test_ui_library_authoring_contracts.py`
- `tests/test_library_character_persona_authoring.py`

No open design decision remains for the shared workspace. User-authored themes
remain a separately scoped backlog feature.
