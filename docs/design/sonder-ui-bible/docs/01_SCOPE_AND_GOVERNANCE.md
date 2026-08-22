# 01. Scope and Governance

## Scope

This bible governs all player-facing and host-facing web UI in Sonder Engine:

- Play workspace and transcript;
- composer and live turn state;
- contextual story tools and inspector surfaces;
- Library, search, filters, story scopes, and asset editors;
- Settings and Advanced settings;
- new-story setup and first-run onboarding;
- authentication, host setup, guest joining, and guest play;
- dialogs, sheets, menus, tooltips, toasts, progress, and activity surfaces;
- extension-hosted UI rendered inside Sonder;
- desktop, tablet, phone portrait, phone landscape, and short-height layouts;
- curated themes and Legacy compatibility;
- structural accessibility and configurable visual-accessibility modes.

## Out of scope

The bible does not redefine:

- story-generation behavior;
- agent roles or prompts;
- world simulation;
- persistence semantics;
- security or authentication policy;
- API contracts except where a UI requirement explicitly needs a presentation endpoint;
- extension business logic.

## Locked architecture

The top-level product architecture is fixed:

- **Play**: current story, transcript, composer, story state, and contextual tools.
- **Library**: stories, characters, personas, lore, reusable material, imports, exports, and associations.
- **Settings**: application experience, AI connections, content preferences, add-ons, maintenance, and advanced controls.

Desktop spatial rule:

> Left is where the user chooses where to go. Center is the current work. Right is where the user adjusts or inspects the current work.

Mobile spatial rule:

> Primary destinations remain persistent; contextual work becomes staged full-screen content or sheets.

## Design authority

A component or screen is conforming only when it follows both:

1. the visual grammar;
2. the interaction and UX grammar.

A visually attractive screen that adds friction is nonconforming. A usable screen that ignores the design system is also nonconforming.

## Deviation policy

A deviation is acceptable only when:

- a real content or platform constraint makes the standard rule unsuitable;
- the alternative is documented before implementation;
- the user impact is explained;
- desktop and mobile implications are covered;
- accessibility and localization implications are covered;
- the deviation does not create a new one-off visual language.

Use [29 Change Control](29_CHANGE_CONTROL.md) to record amendments.

## Review ownership

Every major UI change should receive four explicit reviews:

1. **Product flow review**: does the task make sense for a player?
2. **Visual-system review**: does it use the bible correctly?
3. **Responsive review**: does the hierarchy adapt across supported viewports?
4. **Implementation review**: does the code preserve behavior, state, and extension contracts?

## Definition of finished

A UI feature is not finished when its default screenshot looks acceptable. It is finished when:

- all required states exist;
- novice and expert paths are both viable;
- desktop and mobile are functionally complete;
- alignment and icon geometry pass review;
- long content and localization pass review;
- keyboard, touch, and focus behavior pass review;
- theme and accessibility variants pass review;
- known deviations are documented.
