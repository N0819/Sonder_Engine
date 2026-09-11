# Unbuilt work — Parked

Part of the [unbuilt-work register](UNBUILT.md).

Not scheduled, not committed to a phase. Kept so they are not lost and not
accidentally built. Four feature WISHES that were here — salience-driven
personal lore, per-character retrieval depth, belief-revision salience and an
optional minimap — moved to [`docs/design/IDEAS.md`](design/IDEAS.md) on
2026-08-19; a wish is not a defect, and one earns its way back here only by
someone measuring a live story where its absence makes the engine wrong.

- **An assembled name is not capitalised.** With the phonology lane running,
  a generated body is named from fragments and the fragments are stored as an
  author writes them -- lower case. Measured 2026-08-28 on a two-month
  Enterprise presim, the first generation where the lane was the primary
  source: 28 of 32 bodies came out as `dacuna soforen`, `keitata pioid`,
  `jedisha baroier`. The names are otherwise GOOD -- no canon mashup survived,
  which is what the lane was built for -- so this is presentation and not
  provenance. The rule belongs at assembly rather than at display: a name is
  capitalised the way the setting's own law capitalises, and a law whose
  fragments arrive lower case still yields a name a story can print. Owner
  noted it during that run and parked it deliberately; it does not block a
  playtest.

- **`providers.chat_complete_async` is dead.** Defined and called from nowhere
  but its own retry loop — `web/app.py` no longer imports it either, so the
  only three references in the tree are its own definition, its recursive call
  and `_chat_complete_async_once` (`llm/providers.py`). The threading model
  works and the `contextvars` discipline is built around it, so the
  recommendation is to delete the function rather than build on it.
- **`llm/prompt_cache.py` is dead** — no importer anywhere — and its
  `estimate_cacheable_tokens` heuristic is wrong by 5x to 262x on every stage.
  `AGENTS.md` still names it as the watch-file for cacheability.
- **`agents/common._agent_json`'s docstring** describes the ladder as "one
  temperature-0 repair, then per-candidate fallback" and no longer mentions the
  length escalation added in `c9c1fbe`.

- **A conformance test for `Design.md`.** Its status table is prose. A test
  asserting each "Built" row still resolves to real code — symbol exists, module
  imports, field present — would make that file self-checking the way `make
  structure` keeps `CODE_MAP.md` honest. Highest-leverage idea here: it prevents
  exactly the drift this compilation had to repair.
- **A leak-injection suite.** Deliberately plant a forbidden fact in a character's
  world record and assert it never surfaces in that character's output across N
  turns. The firewall is the engine's central claim and is currently protected by
  construction plus targeted tests.
- **Remove the deprecated macro schema.** `fiction_worlds`, `fiction_locations`
  and `transit_edges` are dead — nothing in the runtime reads or writes them — but
  they are still created, snapshotted, restored and exported. Removal is planned
  and needs a migration.
