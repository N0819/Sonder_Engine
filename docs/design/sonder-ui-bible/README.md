# Sonder UI Design Bible

**Version:** 1.2
**Date:** 2026-08-24
**Status:** Authoritative UI/UX design direction  
**Applies to:** Sonder Engine player-facing web interface, host setup, guest play, extensions hosted inside Sonder, desktop, tablet, and mobile

## Purpose

This package is the canonical design language for Sonder. It gathers the approved visual direction, information architecture, interaction rules, mobile doctrine, component contracts, accessibility choices, control-cluster pattern, quality gates, and reference interpretation into a set of dedicated Markdown documents.

The bible exists to prevent the interface from drifting into one-off styling decisions. A screen is not considered finished because it looks attractive in isolation. It must use the same geometry, alignment, typography, color semantics, interaction grammar, responsive behavior, and UX priorities as the rest of the product.

## North star

> Sonder is a quiet instrument surrounding the story, not a technical display competing with it.

The interface should feel precise, atmospheric, capable, and intentional. It should not feel corporate, toy-like, overly futuristic, or genre-specific. Fantasy, historical, horror, contemporary, romance, mystery, and science-fiction stories must all feel native inside the same shell.

## Authority

For UI and UX decisions, use this order:

1. This design bible.
2. An approved feature-specific design specification that explicitly amends the bible.
3. Current implementation constraints and extension contracts.
4. Existing UI behavior.

For engine behavior, persistence, security, and repository architecture, the maintained repository guidance remains authoritative. This bible does not override engine invariants.

## Normative language

- **MUST**: required for conformance.
- **MUST NOT**: prohibited.
- **SHOULD**: expected unless a documented reason justifies deviation.
- **SHOULD NOT**: normally avoided; exceptions require rationale.
- **MAY**: optional.

## Package map

### Foundation

- [00 North Star](docs/00_NORTH_STAR.md)
- [01 Scope and Governance](docs/01_SCOPE_AND_GOVERNANCE.md)
- [02 Reference Translation](docs/02_REFERENCE_TRANSLATION.md)
- [03 Product Character](docs/03_PRODUCT_CHARACTER.md)
- [04 Experience Principles](docs/04_EXPERIENCE_PRINCIPLES.md)
- [05 Information Architecture](docs/05_INFORMATION_ARCHITECTURE.md)

### Visual system

- [06 Visual Grammar](docs/06_VISUAL_GRAMMAR.md)
- [07 Soft-Precision Geometry](docs/07_SOFT_PRECISION_GEOMETRY.md)
- [08 Spacing, Alignment, and Density](docs/08_SPACING_ALIGNMENT_AND_DENSITY.md)
- [09 Typography](docs/09_TYPOGRAPHY.md)
- [10 Color, Surfaces, and Themes](docs/10_COLOR_SURFACES_AND_THEMES.md)
- [11 Iconography](docs/11_ICONOGRAPHY.md)
- [12 Integrated Control Clusters](docs/12_INTEGRATED_CONTROL_CLUSTERS.md)
- [13 Component Contracts](docs/13_COMPONENT_CONTRACTS.md)

### Product surfaces

- [14 Play Workspace](docs/14_PLAY_WORKSPACE.md)
- [15 Library](docs/15_LIBRARY.md)
- [16 Settings](docs/16_SETTINGS.md)
- [17 New Story and First Run](docs/17_NEW_STORY_AND_FIRST_RUN.md)
- [18 Responsive and Mobile](docs/18_RESPONSIVE_AND_MOBILE.md)
- [19 Accessibility and Personalization](docs/19_ACCESSIBILITY_AND_PERSONALIZATION.md)
- [20 Content and Terminology](docs/20_CONTENT_AND_TERMINOLOGY.md)
- [21 Motion, Sound, and Feedback](docs/21_MOTION_SOUND_AND_FEEDBACK.md)
- [22 UX Flows and Expert Acceleration](docs/22_UX_FLOWS_AND_EXPERT_ACCELERATION.md)

### Governance and review

- [23 Anti-Patterns](docs/23_ANTI_PATTERNS.md)
- [24 Tokens and Measurements](docs/24_TOKENS_AND_MEASUREMENTS.md)
- [25 Audit Rubric and Quality Gates](docs/25_AUDIT_RUBRIC_AND_QUALITY_GATES.md)
- [26 Decision Register](docs/26_DECISION_REGISTER.md)
- [27 Reference Notes](docs/27_REFERENCE_NOTES.md)
- [28 Glossary](docs/28_GLOSSARY.md)
- [29 Change Control](docs/29_CHANGE_CONTROL.md)

### Templates

- [Component Specification Template](templates/COMPONENT_SPEC_TEMPLATE.md)
- [Screen Polish Audit Template](templates/SCREEN_POLISH_AUDIT_TEMPLATE.md)
- [UX Flow Audit Template](templates/UX_FLOW_AUDIT_TEMPLATE.md)

### Checklists

- [Visual Polish Checklist](checklists/VISUAL_POLISH_CHECKLIST.md)
- [UX Flow Checklist](checklists/UX_FLOW_CHECKLIST.md)
- [Responsive Checklist](checklists/RESPONSIVE_CHECKLIST.md)
- [Design Review Release Gate](checklists/DESIGN_REVIEW_RELEASE_GATE.md)

## How to use the bible

Before designing or changing a surface:

1. Read [00 North Star](docs/00_NORTH_STAR.md) and [04 Experience Principles](docs/04_EXPERIENCE_PRINCIPLES.md).
2. Read the relevant product-surface document.
3. Read the relevant visual and component contracts.
4. Create a screen or component specification using the provided template.
5. Review the result with the audit rubric and checklists.
6. Record any approved deviation using [29 Change Control](docs/29_CHANGE_CONTROL.md).

## Relationship to earlier remaster documents

This bible consolidates and refines the earlier Sonder UI remaster specification, visual realignment audit, and approved design discussion. It supersedes their visual-language guidance where the documents differ. Their implementation history and source audit remain useful evidence, but this package is the current design authority.
