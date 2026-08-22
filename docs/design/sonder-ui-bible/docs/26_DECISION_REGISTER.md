# 26. Decision Register

This register records the approved design direction consolidated into the bible. Changes require the amendment process in [29 Change Control](29_CHANGE_CONTROL.md).

| ID | Decision | Locked outcome |
|---|---|---|
| DB-01 | Scope | Full product-wide UI/UX system covering primary and secondary surfaces. |
| DB-02 | Restructuring | Moderate-to-deep restructuring is permitted when justified by clarity or friction. |
| DB-03 | Language | Player-facing language remains clean, plain, and non-corporate. |
| DB-04 | Device priority | Desktop and mobile have equal product priority and feature parity. |
| DB-05 | Primary navigation | Play, Library, Settings. |
| DB-06 | Desktop spatial model | Navigation left, current work center, contextual inspector right. |
| DB-07 | Mobile spatial model | Bottom navigation plus staged full-screen views and sheets. |
| DB-08 | Play | Story-first central workspace with contextual Story Tools. |
| DB-09 | Library | Unified Library with type views and story-scoped collections. |
| DB-10 | Library semantics | Story scopes are filters/associations, not ownership folders. |
| DB-11 | Settings | Experience, AI Connections, Content, Add-ons, Maintenance, Advanced. |
| DB-12 | Palette | Carbon grounds, signal cyan interaction, amber callouts. |
| DB-13 | Themes | Carbon Signal, Ash and Brass, Midnight Ink, Parchment Night, plus Legacy. |
| DB-14 | Surface treatment | Controlled technical glass with solid and performance fallbacks. |
| DB-15 | Typography | Interface sans, literary serif prose/composer, restrained monospace technical role. |
| DB-16 | Iconography | Original genre-neutral SVG family; no emoji/text glyph primary icons. |
| DB-17 | Visual character | Compact technical minimalism with restrained instrumentation and genre neutrality. |
| DB-18 | Sci-fi limit | No cockpit ornament, persistent scanlines, glowing HUD clutter, or franchise imitation. |
| DB-19 | Accessibility | Structural accessibility is mandatory; visual aids use Accessibility Mode plus granular controls. |
| DB-20 | New Story | One guided setup with Describe a Story, Use My Library, Start Blank. |
| DB-21 | Saving | Hybrid saving: autosave low risk, drafts for long work, explicit action for consequential changes. |
| DB-22 | Geometry | Soft-Precision Geometry: 4 px default, controlled 3-5 px range, semantic round only. |
| DB-23 | Bevel | Tonal bevel through border/highlight/shadow, not repeated literal chamfers. |
| DB-24 | Control grouping | Integrated Control Clusters are preferred for related controls. |
| DB-25 | Cluster limits | Clusters clarify one task, retain per-segment state, do not wrap, and move low-frequency actions to More. |
| DB-26 | Accent discipline | Cyan and amber are signals, not general decoration. |
| DB-27 | Index discipline | Indices organize major destinations/tools/sequences, not ordinary controls. |
| DB-28 | Expert access | Keyboard shortcuts, pinned tools, recents, search, and compact density accelerate experts without cluttering novice defaults. |
| DB-29 | Mobile adaptation | Mobile reprioritizes and stages content rather than compressing desktop. |
| DB-30 | Quality governance | Alignment, state, responsive, UX, and accessibility audits are release gates. |

## Interpretation rules

1. Story readability wins over reference imitation.
2. Plain language wins over technical aesthetics.
3. Feature parity wins over visual minimalism.
4. Stable locations win over novelty.
5. Genre neutrality wins over stronger sci-fi identity.
6. A legacy theme or extension may adapt to the host, but may not redefine core component semantics.
7. A deviation must be explicit; silent drift is nonconforming.
