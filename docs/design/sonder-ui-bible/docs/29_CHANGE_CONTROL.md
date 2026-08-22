# 29. Change Control

## Purpose

The bible is intended to evolve, but not through silent one-off implementation decisions.

## Amendment categories

### Clarification

Explains an existing rule without changing its intent.

### Calibration

Adjusts a value such as color, spacing, width, or timing after visual testing while preserving the system.

### Extension

Adds a new component, state, or pattern consistent with existing principles.

### Exception

Allows a specific surface to deviate because of a documented constraint.

### Revision

Changes a locked design decision or system principle.

## Amendment record

Every amendment should include:

- identifier;
- date;
- author/reviewer;
- category;
- affected documents and sections;
- current rule;
- proposed rule;
- rationale;
- screenshots or evidence;
- desktop impact;
- mobile impact;
- accessibility impact;
- localization impact;
- migration impact;
- approval status.

## Approval level

- Clarification and calibration: design review.
- Extension: design and implementation review.
- Exception: design review plus explicit scope and expiration/reassessment date.
- Revision: product-owner approval.

## Exception rules

An exception must be narrow. It must not become a reusable precedent unless promoted to an extension or revision.

Example:

> A code editor may use 2 px radius inside an existing 5 px editor frame because its scrollable canvas is visually structural. This does not authorize 2 px buttons elsewhere.

## Review cadence

Review the bible after:

- a major UI release;
- the introduction of a new destination or editor family;
- repeated audit findings in the same component category;
- major mobile changes;
- a new curated theme;
- substantial extension-host changes;
- user research that contradicts a current assumption.

## Deprecation

When a pattern is replaced:

- mark it deprecated;
- identify replacement;
- define migration scope;
- prevent new usage;
- remove or update examples;
- retain a short historical note only when it helps avoid regression.

## Versioning

Use semantic bible versions:

- major: locked design direction changes;
- minor: new component families or substantial extensions;
- patch: clarifications and calibration.
