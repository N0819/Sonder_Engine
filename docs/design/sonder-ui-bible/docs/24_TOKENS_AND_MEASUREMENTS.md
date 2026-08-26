# 24. Tokens and Measurements

## Core tokens

```css
--sonder-radius: 4px;
--sonder-border: 1px;

--sonder-topbar-h: 40px;
--sonder-module-bar-h: 30px;
--sonder-composer-min-h: 56px;

--sonder-left-dock-width: min(286px, 18vw);
--sonder-right-dock-width: min(286px, 18vw);
--sonder-dock-min: 200px;
--sonder-dock-max: 420px;
--sonder-reading-width: clamp(320px, 43vw, 680px);
--sonder-prose-width: 650px;
```

## Typography

```css
--sonder-font-ui: "Geist Sans", "Segoe UI", sans-serif;
--sonder-font-mono: "Geist Mono", Consolas, monospace;
--sonder-font-prose: Newsreader, Georgia, serif;

--sonder-text-micro: 9px;
--sonder-text-detail: 10px;
--sonder-text-module: 11px;
--sonder-text-nav: 12px;
--sonder-text-local-title: 13px;
--sonder-text-prose: 15px;

--sonder-line-micro: 12px;
--sonder-line-detail: 14px;
--sonder-line-nav: 16px;
--sonder-line-local-title: 17px;
--sonder-line-prose: 1.62;
```

## Deep Current colors

```css
--sonder-ink: #06090a;
--sonder-panel-rgb: 4 7 8;
--sonder-handle-rgb: 7 11 12;
--sonder-chrome-rgb: 11 18 19;
--sonder-text-rgb: 239 244 241;
--sonder-ambient-rgb: 148 217 208;

--sonder-ready: #86ef79;
--sonder-source: #d2b57a;
--sonder-error: #df7b70;

--sonder-line-top: rgb(236 248 244 / 14%);
--sonder-line-low: rgb(0 0 0 / 54%);
--sonder-line-soft: rgb(229 245 239 / 8.5%);
```

## Material defaults

```css
--sonder-glass-density: 0.20;
--sonder-bar-opacity: 0.60;
--sonder-selected-strength: 0.06;
--sonder-frost-level: 12px; /* 50% of the 0-24px control */

--sonder-text: rgb(var(--sonder-text-rgb) / 88%);
--sonder-muted: rgb(var(--sonder-text-rgb) / 46%);
--sonder-faint: rgb(var(--sonder-text-rgb) / 27%);
```

All four material controls expose 0-100% input. Implement density and opacity
through alpha-bearing colors, never ancestor opacity.

## Ambient defaults

```css
--sonder-ambient-x: 68%;
--sonder-ambient-y: 38%;
--sonder-ambient-radius: 54%;
--sonder-ambient-strength: 0.64;
```

## Motion

```css
--sonder-duration-fast: 120ms;
--sonder-duration-tab: 150ms;
--sonder-duration-reflow: 190ms;
--sonder-duration-dock: 260ms;
--sonder-ease: cubic-bezier(.22, .78, .22, 1);
```

## Character roster

```css
/* portrait / row */
--sonder-roster-compact: 0px / 28px;
--sonder-roster-standard: 47px / 52px;
--sonder-roster-medium: 72px / 78px;
--sonder-roster-large: 96px / 102px;
--sonder-roster-portrait: 141px / 147px;
```

Implement these as paired tokens rather than literal slash syntax.

## Responsive references

```css
/* constrained workbench */
@media (max-width: 1180px) { /* docks target 230px */ }

/* compact workbench */
@media (max-width: 860px) { /* docks stage closed/overlay */ }

/* phone */
@media (max-width: 680px) { /* top shelf prioritizes workspace cells */ }
```

Shelf capacity:

```js
Math.max(2, Math.min(4, Math.floor((usableDockHeight + 20) / 420)))
```

## Layer bands

Use named layers in this order:

1. canvas;
2. story;
3. docked material;
4. sticky top shelf/composer;
5. floating modules;
6. drag previews and drop rails;
7. menus/sheets;
8. modal;
9. notices.

Arbitrary local z-index escalation is nonconforming.
