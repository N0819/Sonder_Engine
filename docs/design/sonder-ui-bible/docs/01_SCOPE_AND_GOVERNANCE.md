# 01. Scope and Governance

## Scope

This bible governs all player-facing and host-facing web presentation:

- the global shell and top shelf;
- Scene, transcript, composer, story status, and atmospheric canvas;
- modular left/right toolbars, shelves, tabs, floating modules, and Widget Shelf;
- Library, Settings, New Story, authentication, guest play, and editors;
- color, canvas, glass, typography, geometry, motion, and accessibility;
- desktop, tablet, phone, short-height, keyboard, pointer, and touch behavior;
- extension UI mounted into the Sonder shell.

It does not redefine engine simulation, model prompts, storage, security,
authentication policy, archive semantics, or extension business logic.

## Canonical architecture

The product has three primary workspaces:

- **Scene**: current story, prose, composer, atmospheric stage, and immediate
  story operation.
- **Library**: stories, Characters, Personas, Lore, associations, archives,
  imports, exports, and reusable material.
- **Settings**: application configuration, appearance, accessibility, AI
  Connections, providers, content preferences, add-ons, maintenance, and
  advanced controls.

They occupy centered cells in one top shelf. No left navigation rail, mobile
bottom navigation, or second primary-destination system is conforming.

## Modules and ownership

Ownership describes where a capability is authored and rediscovered, not where
its module may sit. Eligible Library and Settings sections may be docked beside
Scene. One module has one live instance and one state owner. Docking, tabbing,
floating, or storing a module never duplicates its controls or data binding.

## Authority

Design Bible 2.0 and the committed Atmospheric Workbench jointly own
presentation. The artifact controls composition and interactions it
demonstrates; this bible controls the system and states it does not show. A
later approved feature specification may explicitly revise either. Maintained
interface/runtime contracts follow for integration, while existing
implementation and historical UI evidence remain last.

Runtime disagreements resolve to current source, schemas, maintained guides,
and tests. A port may adapt the connection between UI and runtime; it may not
redesign the visible result for implementation convenience.

## Historical material

The previous progressive-redesign amendment is retired. Earlier screenshots,
candidate implementations, work-package reviews, and version 1.x chapters are
historical evidence only. They may identify capabilities and failure modes, but
they cannot restore a rail, inspector, numbered navigation, fixed theme set, or
other conflicting presentation.

## Definition of finished

A UI change is complete only when:

- the relevant workbench composition matches the canonical artifact at the
  same viewport;
- all operations preserve current runtime authority;
- docking and module moves have pointer, keyboard, and menu routes;
- focus, state, error, saving, and recovery behavior are complete;
- default, solid, reduced-motion, high-contrast, long-label, and responsive
  states are reviewed;
- no old component family survives beside the new one as a hidden duplicate;
- any deliberate divergence is recorded under change control.
