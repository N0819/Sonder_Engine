# 29. Change Control

## Purpose

Design Bible 2.0 is a coherent system. Changes must not reintroduce a rejected
1.x pattern through a local implementation shortcut.

## Change categories

### Calibration

Adjusts a token such as color, opacity, timing, or measurement after evidence
without changing the workbench model.

### Extension

Adds a module or component that uses existing ownership, material, geometry,
and interaction rules.

### Exception

Allows one bounded surface to diverge because of a documented platform,
security, or content constraint.

### Revision

Changes a locked outcome such as primary navigation, module ownership, docking,
font roles, texture policy, theme model, or geometry.

## Required record

Every approved change records:

- identifier and date;
- category and owner;
- affected Bible decisions/files;
- current and proposed outcome;
- reason and user benefit;
- canonical-artifact impact;
- desktop, height, compact, and mobile impact;
- accessibility/localization impact;
- runtime and migration impact;
- same-viewport evidence;
- approval status.

## Artifact synchronization

If a calibration or revision changes visible canonical behavior, update the
reference artifact or provide a new frozen reference in the same change. Record
its SHA-256 values in [27 Reference Notes](27_REFERENCE_NOTES.md) and regenerate
the package manifest.

Implementation screenshots never silently replace the canonical artifact.

## Revision threshold

Product-owner approval is required before any of these changes:

- a fourth primary workspace;
- left rail, bottom navigation, or default inspector;
- multiple live copies of one module;
- nested horizontal docking or unbounded IDE layout;
- a new font role or geometry family;
- CRT grain, scanline, noise, shimmer, or persistent material animation;
- story-title switching outside Library;
- material controls that do not reach their documented bounds.

## Deprecation

When replacing a pattern:

1. remove it from every normative chapter, example, checklist, and template;
2. update maintained authority guides;
3. retain only a short non-normative tombstone where an old link must survive;
4. prevent new use through review/tests;
5. migrate current implementation without preserving hidden duplicates.

## Versioning

- major: composition or locked-system revision;
- minor: coherent new module/component family;
- patch: clarification or token calibration.
