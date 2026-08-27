# 09. Adoption and Change Control

## Revision category

Panels, Widgets, and the Widget Catalog constitute a **Revision** under the
current Design Bible change-control policy. They alter locked primary
navigation, workspace identity, module multiplicity, and Widget Shelf behavior.

This package remains a proposed feature specification until the authoritative
files and canonical artifact are updated together.

## Adoption outcome

Adoption means:

- Panel tabs replace fixed Scene/Library/Settings cells;
- Scene, Library, and Settings become shipped editable Panel definitions;
- the Widget Catalog replaces the Widget Shelf as discovery and recovery
  authority;
- all eligible front-facing surfaces register through one Widget contract;
- built-in Widget identity and control chrome use the accepted manifest-backed
  Minimal UI SVG collection and semantic mapping;
- strict active-story context replaces any story-specific Panel set or pinned
  Widget concept;
- current server and runtime ownership remain unchanged.

## Authoritative documentation impact

The following current Design Bible files require coordinated revision when the
product owner adopts this package:

- `README.md` — purpose, locked frame, package map, and conformance rule;
- `docs/00_NORTH_STAR.md` — workbench description;
- `docs/01_SCOPE_AND_GOVERNANCE.md` — authority and definition of finished;
- `docs/05_INFORMATION_ARCHITECTURE.md` — primary navigation, Panels, defaults,
  and Widget Catalog;
- `docs/13_COMPONENT_CONTRACTS.md` — Panel tabs, Widget chrome, icon mapping,
  Catalog drawer, browser, slots, stacks, and placement;
- `docs/14_SCENE_WORKSPACE.md` — convert Scene from destination doctrine to the
  shipped story-stage Panel;
- `docs/15_LIBRARY.md` — convert Library from destination to default Panel and
  global Widget projection;
- `docs/16_SETTINGS.md` — convert Settings from destination to default Panel
  and group/panel Widgets;
- `docs/18_RESPONSIVE_AND_MOBILE.md` — responsive Panel tabs and Catalog;
- `docs/19_ACCESSIBILITY_AND_PERSONALIZATION.md` — Panel and placement keyboard
  model;
- `docs/20_CONTENT_AND_TERMINOLOGY.md` — Panel, Widget, Widget Catalog, slot,
  template, and replacement of Module/Widget Shelf language;
- `docs/22_UX_FLOWS_AND_EXPERT_ACCELERATION.md` — Panel creation/switching,
  catalog discovery, placement, reset, and story switching;
- `docs/23_ANTI_PATTERNS.md` — fixed-destination restoration, story pinning,
  duplicate registries, and drag-only placement;
- `docs/24_TOKENS_AND_MEASUREMENTS.md` — Catalog and Panel-tab measurements;
- `docs/25_AUDIT_RUBRIC_AND_QUALITY_GATES.md` — new responsive and behavioral
  gates;
- `docs/26_DECISION_REGISTER.md` — revision and supersession records;
- `docs/28_GLOSSARY.md` — new canonical terminology;
- `docs/29_CHANGE_CONTROL.md` — version/adoption record where necessary.

The maintained `docs/guides/INTERFACE.md` must change in the same implementation
commit as the runtime boundary. It currently names exactly three destinations,
route-driven layout state, and destination-specific consumers.

## Canonical artifact impact

The current Atmospheric Workbench artifact demonstrates fixed Scene, Library,
and Settings cells and a small Widget Shelf. Adoption requires a new or revised
canonical artifact showing at minimum:

- several Panel tabs plus New Panel;
- real collection SVG identity/action icons with the accepted icon-versus-label
  treatment;
- editable shipped default Panel state;
- the trailing Widgets launcher;
- compact catalog drawer;
- expanded Visual catalog over blurred background;
- expanded Compact catalog;
- category filtering and search;
- automatic and explicit placement;
- contextual `Fits this slot` launch;
- no-story active-story Widgets;
- desktop, constrained, tablet, phone, short-height, and reduced-motion states.

The artifact must be frozen and checksummed under the existing reference-note
process. Work-in-progress screenshots do not silently become authority.

## Required runtime investigation before implementation

Documentation adoption does not decide implementation seams. Before a plan is
approved, source investigation must identify:

- current route and navigation-state ownership to retire or adapt;
- current Widget Shelf and docking state envelope;
- active-story selection and refresh coordinator;
- server or local persistence owner suitable for global Panels;
- every Widget's real runtime owner and teardown behavior;
- draft ownership that must outlive Widget unmount;
- extension UI v2 registration and teardown changes;
- manifest-backed semantic icon selection, sanitization, sprite assembly, and
  provenance verification;
- migration from fixed destination routes to Panel identity;
- release-fingerprint propagation for all UI asset changes.

## Staged adoption

A safe implementation may be decomposed, but no stage may create a second
permanent navigation or catalog architecture.

Suggested dependency order:

1. Widget registry and manifest contract;
2. versioned global Panel envelope and migration harness;
3. Panel-tab shell using shipped Scene/Library/Settings definitions;
4. layout zones, placement, Undo, and recovery placeholders;
5. compact Widget Catalog drawer;
6. expanded Visual/Compact browser;
7. built-in Widget conversions by owner group;
8. Settings group/panel decomposition;
9. extension Widget registration;
10. responsive, accessibility, migration, and release qualification.

This sequence is informative rather than an implementation plan. A later plan
must derive tasks from current source and approved template/calibration
decisions.

## Adoption review evidence

Adoption review must include:

- same-viewport comparison to the revised canonical artifact;
- exact Widget inventory coverage;
- story-switch atomicity across visible active-story Widgets;
- no story identifiers in saved active-story Widget configuration;
- Panel reset proving product data and Settings are untouched;
- catalog parity between drawer and expanded browser;
- Visual/Compact parity;
- pointer, keyboard, touch, and menu placement;
- missing-extension and schema-migration recovery;
- desktop, tablet, phone, landscape, short-height, 200% zoom, long-label,
  reduced-motion, solid-surface, and high-contrast review;
- no hidden duplicate controls or parallel server truth;
- every built-in product-chrome icon resolves through the approved local
  manifest and semantic mapping, with no generated substitutes;
- current runtime, security, authentication, and extension contract evidence.

## Deprecation targets

Once adopted and implemented, retire rather than preserve:

- fixed Scene/Library/Settings top-shelf destination cells;
- destination-only assumptions in the shell;
- the small recovery-only Widget Shelf inventory;
- separate catalog lists for drawer, expanded view, Settings, Library, or
  extensions;
- story-specific Panel sets;
- Widget story pinning;
- drag-only placement;
- hidden duplicate source controls used to maintain old navigation.
