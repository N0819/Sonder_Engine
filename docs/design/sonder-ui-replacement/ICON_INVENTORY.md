# Sonder replacement icon inventory

**Asset:** `static/assets/icons/sonder-icons.svg`  
**Delivery:** local external SVG sprite, no build step or network dependency  
**Source:** adapted from the supplied UI-revision candidate at `73a380a0df2f6b139c98d66da9005489bd549d1d`; reviewed and adopted into the replacement under the repository's documented project provenance.  
**Construction:** 24 × 24 view boxes, geometric monoline paths, `currentColor`, 16/20/24 CSS display grids.

Decorative instances are `aria-hidden`. An icon that carries its own meaning uses `role="img"` and an accessible label. Icon-only buttons always retain an accessible name and tooltip. Unfamiliar, destructive, or consequential actions retain visible text in product surfaces.

| Family | Symbol IDs | Intended use |
|---|---|---|
| Destinations | `play`, `library`, `settings`, `home` | Primary destinations; visible labels required outside compact navigation |
| Story tools | `tools`, `cast`, `world`, `style`, `dialogue`, `clothing`, `image`, `ambience`, `story`, `character`, `persona`, `lore`, `prompt` | Product nouns and tool launchers |
| Transport | `send`, `stop`, `retry`, `update`, `recent`, `calendar` | Turn and task actions; stop/retry retain visible text when consequential |
| Discovery | `search`, `filter`, `folder`, `archive`, `favorite`, `sort` | Query, scope, and collection controls |
| Navigation | `menu`, `more`, `close`, `chevron-left`, `chevron-right`, `chevron-down` | Navigation and disclosure; close/more may be icon-only with names/tooltips |
| Editing | `plus`, `minus`, `import`, `export`, `edit`, `delete`, `duplicate`, `save` | CRUD and transfer; delete/import/export retain visible text where consequential |
| Relationships | `link`, `unlink`, `pin`, `unpin`, `resize`, `connection` | Association and pane state |
| System | `theme`, `api`, `extension`, `sound-on`, `sound-off`, `lock`, `unlock`, `offline` | Appearance, provider, extension, sound, and connection state |
| Status | `tasks`, `check`, `warning`, `error`, `info`, `spark` | Always paired with text, state, or shape; never color alone |

The runtime allowlist in `static/js/ui/icons.js` is the executable complete inventory. Removal or renaming requires updating the sprite, allowlist, this record, and icon-system tests together.
