# WP15 alpha 9.8 UI parity review

**Status:** implementation complete; final regression results recorded below

**Engine baseline:** alpha 9.8, `2ac1d162fe69b23c9b7bdbcc6a8efa8e6231c979`

**Interface release:** `alpha98-ui1`

WP15 ports every new alpha 9.8 host-facing capability into the replacement UI.
The engine merge remains the runtime and persistence authority. This package
adds frontend adapters, presentation, localization, browser contracts, and
visual evidence only; it does not introduce or redesign backend architecture.

## Surface placement

| Capability | Canonical replacement surface | Placement decision |
|---|---|---|
| Lived place during Story creation | New Story steps 2 and 3 | Extend the existing focused setup; no alternate wizard |
| Character history during Quick Start | Character authoring Quick Start | Extend the existing save-before-start action |
| Create a place from reusable Lore | Lore detail | Keep the action beside its source, current-Story gated |
| Inspect institutions and upkeep | Dialogue Story Tool | Story-scoped ledger below the existing structural editor |
| Charter diagnostics | Dialogue institution ledger | Native disclosure loaded only when expanded |
| Living-world explanation | Content Settings | Settings retain ceilings only and link to Story Tools |

`static/js/ui-next/lived-location.js` supplies the common authored form and
request mapping. Each consumer retains its existing route, owner, draft, and
save policy. Public resident data and private Character history are disclosed
where the choice is made. Information movement is described as witnessing,
telling, reading, and carrying through the Story—not as a configuration flag.

## Runtime boundary

- New Story and Lore use the released lore attachment and Charter generation
  endpoints. Character Quick Start sends the released alpha 9.8 request body.
- Dialogue reads released Charter summary and diagnostics endpoints. It never
  reconstructs Charter state from prose or settings.
- Settings continues to write only the released living-world settings document.
  The Institution action routes to Dialogue instead of creating a second editor.
- No schema, persistence, world-clock, simulation, or service architecture was
  added by WP15. The alpha 9.8 backend merge is preserved as released.
- All writes retain explicit request owners and current-route checks. The New
  Story draft clears only after every selected post-create step succeeds.

## Reference and responsive comparison

The alpha 9.8 additions retain the supplied reference composition: flat
structural forms and ledgers, quiet borders, restrained cyan, compact metadata,
native disclosure staging, and the existing desktop inspector/mobile sheet
geometry. No dashboard, card grid, new destination, or parallel inspector was
introduced.

Recorded same-viewport browser evidence:

- [New Story lived location](../wp09/screenshots/new-story-lived-location-1440.png)
- [Dialogue institution ledger](../g3/story-tools/screenshots/desktop-institutions.png)
- [Living-world Settings boundary](../wp08/screenshots/settings-content-living-world-1440.png)
- [Medium Lore detail](../g4/library/screenshots/medium-lore-detail.png)
- full regenerated Shell, Story Tools, and Library matrices under `g2/`, `g3/`,
  and `g4/`

The comparison found no deliberate Design Bible deviation. The new shared form
uses the existing semantic controls and 44-pixel compact target contract;
Story Tools keep the reference right-rail density and scroll ownership; Library
keeps its ledger/detail staging. Institution and Story names remain marked as
engine data rather than translated interface copy.

## Behavioral evidence

- New Story request normalization, review disclosure, 16-Character guard,
  incomplete-Story cleanup, and retained recovery link
- Quick Start exact `lorebook_id`, `already_known`, `language`, and
  `lived_location` request contract
- current-Story/current-frame Lore generation with captured item and route
- Dialogue Charter summary, warnings, diagnostics, and generation disclosure
- Settings information boundary and canonical Institution-tools route
- complete English/Japanese catalog parity and one `alpha98-ui1` module graph

## Qualification

Focused alpha 9.8 browser suite: 57 passed. Release/source contracts: 63 passed.
English/Japanese catalog and language-pack suite: 40 passed. Project structure
check passed. The exact-source qualification run completed with 8,797 Python
tests passed and 4 platform-specific tests skipped, plus 186 browser tests
passed. These results were recorded before integration into `interface`.
