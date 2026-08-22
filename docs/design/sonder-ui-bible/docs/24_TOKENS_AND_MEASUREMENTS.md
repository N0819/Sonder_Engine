# 24. Tokens and Measurements

## Purpose

This document provides the baseline token contract. Implementations may represent tokens in CSS, JavaScript, or theme data, but equivalent components must consume the same semantic values.

## Geometry tokens

```css
--radius-compact: 3px;
--radius-default: 4px;
--radius-panel: 5px;
--radius-round: 999px;

--border-hairline: 1px;
--focus-width-default: 2px;
--focus-width-strong: 3px;
```

## Spacing tokens

```css
--space-0: 0;
--space-1: 2px;
--space-2: 4px;
--space-3: 6px;
--space-4: 8px;
--space-5: 12px;
--space-6: 16px;
--space-7: 20px;
--space-8: 24px;
--space-9: 32px;
--space-10: 40px;
--space-11: 48px;
```

## Control tokens

```css
--control-h-compact: 32px;
--control-h-default: 36px;
--control-h-prominent: 40px;
--control-h-touch: 44px;
--control-h-touch-prominent: 48px;

--icon-box-compact: 16px;
--icon-box-default: 20px;
--icon-box-prominent: 24px;
```

Small 28-30 px controls are permitted in dense desktop-only toolbars. They must not become the ordinary field height.

## Layout reference ranges

| Element | Reference range |
|---|---:|
| Primary desktop rail | 56-72 px compact; optional expanded treatment if approved |
| Library category pane | 220-280 px |
| Library item pane | 300-420 px |
| Context inspector | 320-420 px default; 280-520 px resizable |
| Story measure | 680-760 px default; 720 px reference |
| Desktop page inset | 20-24 px |
| Tablet page inset | 16-20 px |
| Mobile page inset | 16 px; 12 px at narrowest widths |
| Dialog width | content-driven; 440-760 px common; full-screen for complex mobile flows |

These are ranges, not permission for arbitrary values within every component. Each component should choose a stable reference size.

## Typography tokens

```css
--font-ui: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
--font-prose: Charter, "Iowan Old Style", "Palatino Linotype", Georgia, serif;
--font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;

--text-micro: 11px;
--text-meta: 12px;
--text-control: 13px;
--text-ui: 14px;
--text-section: 16px;
--text-page: 21px;
--text-display: 28px;
--text-prose: 17px;
```

Reference line heights:

```css
--lh-micro: 14px;
--lh-meta: 16px;
--lh-control: 18px;
--lh-ui: 20px;
--lh-section: 22px;
--lh-page: 28px;
--lh-display: 36px;
--lh-prose: 1.7;
```

## Carbon Signal semantic tokens

```css
--ground-0: #080b0d;
--ground-1: #0c1114;
--surface-1: #11181c;
--surface-2: #172126;
--surface-3: #1d292f;

--text-1: #e6ecef;
--text-2: #a7b2b7;
--text-3: #77858c;

--border-1: #263238;
--border-2: #35454d;

--accent: #54cfe2;
--accent-soft: rgba(84, 207, 226, 0.14);
--warning: #d5a64a;
--success: #69b98f;
--error: #d56b75;
```

## Surface opacity references

```css
--opacity-chrome-over-backdrop: 0.94;
--opacity-inspector-over-backdrop: 0.90;
--opacity-floating-utility: 0.88;
--opacity-turn-plate: 0.48;
```

Opacity should be implemented through explicit RGBA/color-mix values rather than applying `opacity` to an entire interactive subtree.

## Shadow references

```css
--shadow-panel: 0 8px 24px rgba(0, 0, 0, 0.18);
--shadow-overlay: 0 18px 52px rgba(0, 0, 0, 0.42);
--shadow-inner-top: inset 0 1px 0 rgba(255, 255, 255, 0.025);
```

Ordinary cards and rows should not receive `--shadow-panel` by default.

## Motion references

```css
--duration-fast: 120ms;
--duration-default: 180ms;
--duration-slow: 260ms;
--ease-standard: cubic-bezier(.2, .8, .2, 1);
```

Backdrop dissolves and story-atmosphere transitions may be slower when they do not block interaction.

## Z-index bands

Use named layers rather than arbitrary numbers:

- atmosphere;
- application;
- sticky chrome;
- inspector/sheet;
- modal;
- toast/critical overlay.

A component must not exceed its band merely to win a local stacking conflict. Fix the stacking context at the source.

## Token discipline

The following require review:

- hard-coded color inside a component;
- radius outside 0, 3, 4, 5, or semantic round;
- spacing outside the scale;
- control height outside the contract;
- one-off font family;
- arbitrary z-index;
- inline style for a reusable component;
- state border-width changes;
- SVG-specific margin hacks in usage sites.
