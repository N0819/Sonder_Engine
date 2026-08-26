# Sonder UI Design Bible

**Version:** 2.0

**Date:** 2026-08-25

**Status:** Authoritative UI/UX direction

**Applies to:** Sonder Engine player-facing and host-facing web interfaces

## Purpose

This package defines Sonder's Atmospheric Digital Workbench. It replaces the
earlier rail-and-inspector redesign with the approved modular workbench
calibration. The interface is now designed from one coherent object: a living
canvas, an integrated top shelf, a fixed reading stage, and configurable
left/right toolbars made from translucent digital material.

The bible is normative. Historical screenshots, earlier remaster documents,
the retired progressive-redesign amendment, and the current production layout
remain useful implementation evidence, but they do not authorize conflicting
presentation.

## North star

> Sonder is a quiet fiction instrument made from black digital material,
> suspended over a living atmosphere.

The atmosphere owns the field. Prose remains human and unboxed. Chrome appears
only where the user can operate the system. Charm comes from cohesion,
proportion, material consistency, and subtle response—not ornament.

## Canonical reference

The rendered and interactive authority for this revision is the committed
[Atmospheric Workbench](../../experiments/sonder-atmospheric-workbench/README.md).
Its editable fragment, standalone preview, and docking regression harness are
preserved together. The artifact controls the composition, geometry, material,
and interactions it concretely demonstrates. This bible controls the system's
principles and states the artifact does not show. A later approved change must
name any deliberate departure from either; implementation convenience resolves
neither.

## Authority order

For presentation and interaction:

1. This Design Bible 2.0 and its committed Atmospheric Workbench artifact,
   using the division of authority above.
2. An approved feature specification that explicitly changes this bible.
3. The maintained interface implementation contract for runtime integration.
4. Existing UI presentation and historical evidence.

For persistence, security, engine behavior, localization, accessibility
semantics, extensions, and server ownership, current source and maintained
repository guidance remain authoritative. Port behavior into this composition;
do not preserve obsolete presentation because it already exists.

## Locked product frame

- Primary workspaces are **Scene**, **Library**, and **Settings**.
- They are centered cells inside one integrated top shelf; they have no numeric
  prefixes.
- Scene is the atmospheric story workspace.
- The left and right toolbars are modular docks containing vertical shelves and
  tab groups.
- Library and Settings are both full workspaces and canonical sources from
  which eligible modules can be docked.
- A module has one live instance. Moving it never creates a hidden duplicate.
- The Widget Shelf inventories available, docked, floating, and stored modules.
- Story selection belongs to Library. The story identity in the top shelf is
  informative, not a second switcher.

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

- [14 Scene Workspace](docs/14_SCENE_WORKSPACE.md)
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

Templates and checklists live in `templates/` and `checklists/`.

## Conformance rule

A surface is not conforming because it uses dark glass, small text, or cyan
accents. It must preserve the whole system: top-shelf integration, atmospheric
priority, fixed reading measure, modular ownership, clear docking targets,
4 px rounded bevels, compact typography, theme control, responsive capacity,
and quiet static material. A generic dashboard wearing those ingredients is a
failure.
