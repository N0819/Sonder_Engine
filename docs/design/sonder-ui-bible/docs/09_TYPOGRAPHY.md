# 09. Typography

## Three-role system

Sonder uses three typographic roles:

1. **Interface sans** for navigation, controls, forms, dialogs, Library, and Settings.
2. **Literary serif** for story prose, player input echoes, and the composer.
3. **Restrained monospace** for diagnostics, identifiers, code, numeric technical data, and selected indices.

The roles are semantic. A font is not chosen because a surface looks empty or needs more technical personality.

## Interface scale

This table is the formal, normative interface scale. The default is deliberately
compact for modern high-density desktop displays. Components MUST consume the
semantic size and line-height tokens for their role; they MUST NOT introduce a
one-off numeric font size to make one screen denser or louder. Library details,
Settings copy, inspector text, and equivalent interface prose all use this same
scale. Story prose is the only independent reading scale.

| Role | Size | Weight | Line height | Notes |
|---|---:|---:|---:|---|
| Micro index | 11 px | 500-600 | 14 px | desktop only; nonessential; never primary copy |
| Metadata | 12 px | 450-550 | 16 px | minimum persistent metadata size |
| Compact control | 13 px | 500-600 | 16-18 px | compact desktop controls |
| Default UI | 14 px | 400-500 | 20 px | default body and fields |
| Emphasized UI | 14 px | 600 | 20 px | selected items, strong labels |
| Section heading | 16 px | 600 | 22 px | local sections |
| Page heading | 20-22 px | 600 | 28 px | destination-level heading |
| Display/setup heading | 26-32 px | 550-650 | 34-40 px | onboarding and empty-state focus only |

Mobile should not reduce core UI text below 14 px. Inputs should render at 16 px where needed to prevent mobile browser zoom.

The Larger interface accessibility preference remaps the same roles. It does
not permit individual components to enlarge themselves, and it does not change
the independently configured story-prose size.

## Story typography

Default story settings:

- prose size: 17 px;
- line height: 1.65-1.75;
- reading width: approximately 680-760 px, default 720 px;
- paragraph spacing: 0.75-1.0 em where prose structure permits;
- player-input echo: 0.88-0.94 of prose size;
- composer: same serif family and closely related size.

Story size and interface size remain independently configurable.

## Monospace limits

Monospace is appropriate for:

- `01`, `02`, `FIG. 1`, turn numbers, or diagnostic sequence labels;
- model names and identifiers;
- code or raw JSON;
- token counts, durations, and technical metrics;
- keyboard shortcuts.

Monospace is not appropriate for:

- ordinary navigation labels;
- all headings;
- help text;
- player-facing descriptions;
- button labels without technical meaning;
- large blocks of settings copy.

If more than approximately 15 percent of an ordinary screen's visible text is monospace, review whether the interface has become too technical.

## Uppercase policy

Use uppercase only for:

- very short metadata labels;
- rare status labels;
- compact section codes;
- tiny inspector eyebrow text.

Do not use uppercase for:

- sentences;
- long navigation labels;
- form labels;
- descriptive copy;
- dialog titles;
- primary calls to action.

Letter spacing should be modest. Wide tracking on small text reduces readability and should be reserved for very short labels.

## Heading hierarchy

Every screen should have one page-level heading or an equivalent clear title. Section headings use sentence case and do not sit inside decorative dark bars unless the bar is a real header surface.

Hierarchy is established by:

1. size;
2. weight;
3. spacing;
4. tone;
5. optional index.

Do not establish hierarchy through uppercase and color alone.

## Truncation and wrapping

- Story titles may truncate in persistent headers but must be fully available through title, tooltip, or detail view.
- List titles should wrap before actions are pushed off-screen.
- Button labels should not truncate; use a shorter label or move the action to overflow.
- Form labels may wrap to two lines on mobile.
- Technical identifiers may use middle truncation where the prefix and suffix are meaningful.
- Long localized labels must not overlap icons or chevrons.

## Numeric typography

Use tabular numbers for:

- durations;
- turn counts;
- usage counts;
- model cost/context metrics;
- progress percentages;
- indexed lists where vertical alignment matters.

## Font selection and licensing

Implementation may use bundled open-license fonts or robust system stacks. Font files and licenses must be reviewed separately. The design bible defines roles and metrics, not a proprietary font requirement.
