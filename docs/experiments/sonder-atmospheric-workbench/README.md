# Sonder Atmospheric Workbench Reference

This directory preserves the canonical visual and interaction reference for
[Sonder UI Design Bible 2.0](../../design/sonder-ui-bible/README.md). It began
as an exploratory Play-workspace calibration and was promoted after iterative
review of typography, glass, theming, portraits, toolbars, shelves, tabs,
floating modules, and docking behavior.

The artifact defines target presentation and interaction. It does not call
Sonder APIs and is not itself the production frontend. Production integration
must preserve current runtime, persistence, security, localization,
accessibility, and extension authority while reproducing this result.

## Contents

- `sonder-workbench-calibration.html` — source-form self-contained reference
  fragment, immutable at this revision's recorded hash.
- `sonder-workbench-calibration-preview.html` — standalone browser preview.
- `sonder-drag-regression.html` — focused regression harness for viewport
  height, dock capacity, tab merge/reorder, shelf placement, and floating.

Atmosphere and character portraits are embedded as data URLs. The reference
loads Geist Sans, Geist Mono, and Newsreader from external development URLs;
production must bundle reviewed licensed font files rather than hotlink them.

## Run locally

From the repository root:

```powershell
python -m http.server 8765 --directory docs/experiments/sonder-atmospheric-workbench
```

Open:

```text
http://127.0.0.1:8765/sonder-workbench-calibration-preview.html
```

Run focused interaction checks at:

```text
http://127.0.0.1:8765/sonder-drag-regression.html
```

The preserved checkpoint passed all 14 focused browser regressions and real
pointer checks for three-tab insertion and path-independent title-bar docking.

## Reference hashes

- fragment: `1E827341F69FAC44DC79FD85E7B5F1C55B78C05E90DEE4B8FD59F9A07B6F3F98`
- preview: `C4324CDC55C38FCF9E6B7C9F3852DF2BEF03A1618DE6E07D480F2085133BB165`
- regression: `9BA00EF47EA170F74309D7EE933B8B553D67DE353E6D9DB285FFFF05D3BE2FFD`

## Authority boundary

Use the artifact for macro composition, proportions, material, type,
interaction targets, and signature behavior. Use Design Bible 2.0 for the
generalized rules and states not shown by the seeded fixture. Use current
source and maintained implementation guides for data and effects.

The original calibration brief is retained as
[provenance](../../superpowers/specs/2026-08-24-sonder-atmospheric-digital-workbench-mockup-design.md),
not as a competing scope or authority statement.
