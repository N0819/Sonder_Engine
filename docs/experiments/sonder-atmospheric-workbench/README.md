# Sonder Atmospheric Workbench Mockup

This directory preserves the approved standalone Play-workspace mockup used to
calibrate Sonder's atmospheric digital-workbench direction. It is an
exploratory design artifact, not production UI authority and not a runtime
integration.

## Contents

- `sonder-workbench-calibration.html` — editable self-contained mockup fragment.
- `sonder-workbench-calibration-preview.html` — generated standalone browser
  preview.
- `sonder-drag-regression.html` — focused browser regression harness for dock
  capacity, tab merging and reordering, shelf placement, and floating behavior.

The atmospheric canvas and character portraits are embedded as data URLs so the
artifact cannot lose its local image dependencies. Geist Sans, Geist Mono, and
Newsreader remain external font dependencies.

## Run locally

From the repository root:

```powershell
python -m http.server 8765 --directory docs/experiments/sonder-atmospheric-workbench
```

Then open:

```text
http://127.0.0.1:8765/sonder-workbench-calibration-preview.html
```

Run the focused interaction checks at:

```text
http://127.0.0.1:8765/sonder-drag-regression.html
```

The committed checkpoint passed all 14 focused browser regressions and real
pointer checks for three-tab insertion and path-independent title-bar docking.

## Design context

The original approved calibration brief is
[`docs/superpowers/specs/2026-08-24-sonder-atmospheric-digital-workbench-mockup-design.md`](../../superpowers/specs/2026-08-24-sonder-atmospheric-digital-workbench-mockup-design.md).
Later conversation-driven revisions expanded the artifact into an interactive
docking prototype. Production adoption still requires an explicit feature
specification and reconciliation with the maintained interface contracts.
