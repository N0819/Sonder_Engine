# Sonder Widget Catalog Direct-Drag Correction Plan

> **Execution note:** This plan amends the earlier Catalog mockup plan. The approved Windows 11-style direct-manipulation contract replaces marketplace-style Widget cards and per-result action buttons.

**Goal:** Make every visual Catalog result a small, recognizable render of the Widget itself and make that entire result the pointer and keyboard placement surface.

**Architecture:** Keep the existing nineteen-definition registry, filters, drawer/expanded presentations, Panel persistence, and compatible placement model. Replace only the result renderer and entry interaction: shared Widget skeleton data feeds both workspace modules and inert Catalog miniatures; dragging a result temporarily recedes the Catalog, highlights compatible Panel targets, and restores the Catalog after drop or cancellation.

**Files:**

- `C:\Users\Keptin\.codex\visualizations\2026\08\26\01a03c25-da39-77b0-8f05-2dacee25d0a8\panel-build-staging\sonder-workbench-calibration.html`
- `C:\Users\Keptin\.codex\visualizations\2026\08\26\01a03c25-da39-77b0-8f05-2dacee25d0a8\panel-build-staging\sonder-drag-regression.html`
- Approved localhost source and rendered preview under the 2026-08-25 visualization directory

## Task 1: Protect the corrected contract

- Replace tests for `Add` and `Choose placement` actions with tests that assert visible Widget miniatures, zero per-result buttons, whole-result drag sources, singleton unavailable state, direct pointer placement, and Space/arrow/Enter keyboard placement.
- Run the harness before implementation and confirm the new assertions fail for the current marketplace cards.

## Task 2: Build shared miniature Widgets

- Expand the representative Widget skeleton data so all nineteen definitions have distinct front-facing content.
- Render that content inside a miniature with the same module header/body hierarchy as a placed Widget.
- Preserve each definition's footprint family in the expanded Catalog grid and in the drawer.
- Render compact results as draggable names-first rows with a small Widget identity sample, not action controls.

## Task 3: Make the preview the placement control

- Start pointer placement after a movement threshold anywhere on an available result.
- Lift a drag proxy, recede the Catalog, highlight compatible Panel targets, and track the active target beneath the pointer.
- Commit on pointer release over a target and restore the Catalog in its prior drawer/expanded state.
- Support Space to pick up, arrows to select targets, Enter to place, and Escape to cancel.
- Mark Panel singletons already present as visibly unavailable without a fake `On Panel` button.

## Task 4: Verify the localhost artifact

- Run the complete regression harness.
- Compare drawer, expanded desktop, compact, active drag, and phone states in the browser.
- Regenerate the rendered preview from the editable source and confirm no obsolete per-result action controls remain.
