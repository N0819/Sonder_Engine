# UI reference and porting contract

This guide makes the source material for Sonder's full interface replacement
unambiguous. It supplements [`INTERFACE.md`](INTERFACE.md): that guide owns the
implemented frontend boundary, while this guide identifies what the replacement
must look and feel like and how the supplied implementation is reused.

## Approved reference set

### Design authority

- [`docs/design/sonder-ui-bible/README.md`](../design/sonder-ui-bible/README.md)
  is the checked-in Sonder UI Design Bible 1.0 package.
- Its [`MANIFEST.md`](../design/sonder-ui-bible/MANIFEST.md) records the
  per-file SHA-256 values for the imported package.
- The surface chapters, component contracts, responsive rules, tokens, audit
  rubric, checklists, and change-control chapter are normative for UI work.

### Visual composition authority

The supplied `Sonder_UI_Design_Bible_Revision_Screenshots.zip` is the approved
rendered reference. Its SHA-256 is
`299ad1fbb7edd60255f2cd2bf160e43479fc382a355be9218f60308983d94fe0`.

The set contains:

- `01_desktop_play.png`
- `02_desktop_library.png`
- `03_desktop_settings.png`
- `04_desktop_new_story.png`
- `05_desktop_login.png`
- `06_mobile_guest_join.png`
- `07_desktop_empty_play.png`
- `08_desktop_dialog.png`
- `09_mobile_play.png`
- `10_mobile_library.png`
- `11_mobile_settings.png`
- `12_mobile_narrow_play.png`
- `13_mobile_landscape_play.png`
- `14_tablet_library.png`
- `15_tablet_play.png`
- `16_short_settings_advanced.png`
- `00_contact_sheet.png`

On the project owner's workstation the archive was supplied at
`C:\Users\Keptin\Downloads\Sonder_UI_Design_Bible_Revision_Screenshots.zip`.
Treat the filename and hash as identity; do not assume that absolute path is
portable. If the archive is unavailable, do not make or approve visual changes
to a covered surface from memory or from replacement screenshots.

### Reference implementation

The supplied `Sonder_Engine_UI_Design_Bible_Revision-main.zip` is the preferred
source for reproducing the rendered reference. Its SHA-256 is
`52a1ef6c1bbf46f30cc54c1e0d1c3f576635cda81434d048e09d3e9a8a120dc3`.
The candidate audit identifies its implementation baseline as
`73a380a0df2f6b139c98d66da9005489bd549d1d` and revision branch as
`feature/design-bible-revision`.

On the project owner's workstation the archive was supplied at
`C:\Users\Keptin\Downloads\Sonder_Engine_UI_Design_Bible_Revision-main.zip`.
The highest-value visual source begins with:

- `static/index.html`
- `static/css/remaster-tokens.css`
- `static/css/remaster-components.css`
- `static/css/remaster-shell.css`
- `static/css/remaster-entry.css`
- `static/assets/icons/sonder-icons.svg`
- `static/js/remaster/library.js`
- `static/js/remaster/shell.js`
- `static/js/remaster/inspector.js`
- `static/js/remaster/settings.js`

The file-level disposition and current target for each candidate artifact is in
[`CANDIDATE_SALVAGE_LEDGER.md`](../design/sonder-ui-replacement/CANDIDATE_SALVAGE_LEDGER.md).
The broader evidence review is
[`SONDER_UI_DESIGN_BIBLE_ADOPTION_AUDIT_2026-08-21.md`](../design/SONDER_UI_DESIGN_BIBLE_ADOPTION_AUDIT_2026-08-21.md).

### Supporting provenance

- The original `Sonder_UI_Design_Bible_1.0_2026-08-20.zip` has SHA-256
  `a3d8b18e24babfa45ac6888aa6453067dd621ade73af55bdd2e9bbfa44d063d4`.
- The supplied `README(20260821-134753).md` identifies Design Bible 1.0 as the
  authoritative UI/UX direction.
- The supplied `21_DESIGN_BIBLE_REVISION_AUDIT.md` identifies the candidate
  baseline, evidence set, and claimed release result. Its claims are evidence,
  not a substitute for verification against current Sonder.
- The full replacement program is
  [`2026-08-21-sonder-ui-full-replacement-design.md`](../superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md).

## Authority by question

| Question | Authority |
|---|---|
| What should the interface look like at a covered viewport? | Supplied reference screenshot, interpreted with the Design Bible and matching candidate CSS/markup. |
| How should the same design extend to an uncovered state or viewport? | Design Bible, nearest reference states, and existing reference component grammar. |
| Which information and actions appear, and how are they staged? | Design Bible plus supplied reference; an approved feature specification may add required current capabilities without restyling the composition. |
| What owns data, writes, authentication, async lifetime, localization, or extension behavior? | Current source, schemas, APIs, tests, and maintained repository guides. |
| Which candidate mechanism may be copied? | The salvage ledger, confirmed against current contracts. |
| May the visible result differ for implementation convenience? | No. Only an approved specification or recorded Design Bible deviation may authorize a deliberate difference. |

This separates presentation authority from runtime authority. It does not rank
the current replacement's appearance above the supplied reference merely
because the replacement is newer.

## Required porting method

For each surface:

1. Inventory the matching screenshot states and candidate files.
2. Map each reference region, control cluster, and responsive transition to a
   current runtime owner.
3. Port the reference DOM hierarchy, component grammar, measurements, and CSS
   as the starting implementation. Use current shared primitives only where
   they reproduce that result.
4. Replace stale behavioral seams with current services and server APIs without
   changing visible composition.
5. Add current capabilities in the location and staging that best follows the
   reference grammar. Do not default to an unrelated inspector, dashboard, or
   generic form layout.
6. Render the same state and viewport as the supplied screenshot and compare
   them side by side. Check macro geometry before component polish.
7. Verify compact, tablet, desktop, short-height, zoom, keyboard, touch,
   localization, loading, error, empty, and populated behavior as applicable.
8. Record approved differences with requirement, reason, impact, owner, and
   evidence before calling the surface conforming.

## Visual comparison order

Review in this order so local polish cannot conceal structural drift:

1. viewport and primary shell regions;
2. rail width, side-pane width, workspace measure, and inspector presence;
3. region order, headings, action placement, and content hierarchy;
4. responsive staging and what becomes full-screen or bottom navigation;
5. density, spacing, alignment, dividers, and radii;
6. type scale, weight, labels, indexes, icon treatment, and colors;
7. interaction, focus, loading, empty, error, and destructive states.

A different macro composition is a failed comparison even if its colors,
tokens, accessibility checks, and functional tests pass.

## Prohibited shortcuts

- Do not use a screenshot of the current work as the design reference.
- Do not summarize the reference from memory when its source is available.
- Do not claim conformance from token similarity alone.
- Do not preserve invented presentation because code or tests already exist;
  preserve the valid behavior and replace the presentation.
- Do not copy candidate polling, `window.S`, synthetic clicks, hidden legacy
  controls, unsafe `innerHTML`, or obsolete API assumptions.
- Do not let a generic reusable component override the reference composition.
- Do not close visual review without same-viewport browser evidence.
