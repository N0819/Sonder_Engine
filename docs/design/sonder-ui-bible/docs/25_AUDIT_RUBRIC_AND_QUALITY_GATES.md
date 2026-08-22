# 25. Audit Rubric and Quality Gates

## Audit model

Every screen and major component is reviewed in six dimensions:

1. Visual system conformance.
2. Alignment and optical polish.
3. UX clarity and flow.
4. Responsive behavior.
5. Accessibility and input method.
6. State completeness and reliability.

## Severity

### P0 -- Broken

- data loss or security regression;
- inaccessible core workflow;
- application cannot boot or navigate;
- essential capability absent on desktop or mobile;
- destructive action targets the wrong object;
- overlapping controls prevent use;
- save state lies or loses work.

### P1 -- High friction

- primary action unclear;
- frequent action buried unpredictably;
- mobile layout unusable;
- focus trap or restoration failure;
- severe alignment or overflow defect;
- theme/accessibility mode breaks the surface;
- major design-bible violation repeated across a component family.

### P2 -- Polish

- visible misalignment;
- inconsistent spacing or radius;
- icon optical issue;
- weak copy;
- nonblocking state inconsistency;
- localized layout problem;
- excessive visual noise.

### P3 -- Refinement

- optional motion tuning;
- subtle tone or shadow calibration;
- minor density improvement;
- secondary metadata refinement.

No P0 may remain. No P1 may remain without an explicit approved release deviation.

## Visual conformance review

Check:

- 3-5 px geometry;
- no unexplained pills or large radii;
- spacing tokens;
- exact peer control heights;
- common alignment axes;
- sparse accent use;
- surface hierarchy;
- controlled glass;
- typography roles;
- restrained indexing;
- no emoji/text glyph icons;
- control clusters used appropriately;
- no state-induced layout shift.

## Optical review

At 100 and 200 percent zoom, verify:

- icon visible sizes match;
- icon centers align;
- labels share baseline;
- chevrons and trailing actions align;
- badges do not float;
- separators have equal insets;
- selected indicators are centered;
- borders remain one pixel where intended;
- focus ring follows geometry;
- no half-pixel blur from transforms.

## UX review

For each surface, answer:

- What is the user trying to accomplish?
- Is the next action obvious?
- Is the most frequent action within one action from context?
- Are secondary actions predictable?
- Does the screen expose implementation concepts too early?
- Is work preserved on error or Back?
- Is save state visible?
- Is a destructive action clearly separated?
- Can a new user recover from empty and error states?
- Can an experienced user move quickly without cluttering the default state?

## State matrix

Every component family must be checked in:

- idle;
- hover;
- active/pressed;
- focus-visible;
- selected/current;
- disabled;
- loading;
- saving;
- saved;
- save failed;
- validation error;
- warning;
- success;
- destructive;
- empty;
- no results;
- offline;
- unavailable/permission-restricted;
- reduced motion;
- solid surfaces;
- high contrast;
- large UI and prose text;
- long localized content.

## Screenshot matrix

Capture representative screenshots at:

- 1440 x 900;
- 1280 x 800;
- 1024 x 768;
- 768 x 1024;
- 430 x 932;
- 390 x 844;
- 360 x 800;
- 844 x 390;
- 1024 x 600.

For each major surface, include:

- populated state;
- empty state;
- loading or background task;
- error/validation state;
- long-name or localization stress state;
- default and Accessibility Mode where relevant.

## Required user journeys

- host setup and sign-in;
- connect AI provider;
- create story through each setup route;
- continue and stop a turn;
- edit/reroll/version a turn;
- open and pin Story Tools;
- attach/detach Library material;
- create/import/export each asset type;
- edit long character/persona/lore content;
- search and filter Library;
- change theme, density, and accessibility settings;
- install/disable extension;
- run update/backup/maintenance action;
- join and play as guest;
- perform all journeys on mobile.

## New-user audit

Use a tester or review stance with no knowledge of Sonder's internals. Measure:

- time to identify the primary destinations;
- time to create/open a story;
- concepts that require explanation;
- places where the user hesitates;
- misleading labels;
- dead ends;
- errors without recovery.

## Expert-user audit

Use repeat workflows and measure:

- number of actions to frequent tools;
- keyboard path availability;
- persistence of pane and filter state;
- action-cluster efficiency;
- whether More hides frequent actions;
- whether compact density remains legible;
- whether search/Go To reduces repeated navigation.

## Completion evidence

A release design review should include:

- annotated screenshots;
- open-findings list by severity;
- state matrix results;
- responsive matrix results;
- keyboard and touch notes;
- theme and accessibility review;
- known deviations;
- before/after evidence for corrected component families.
