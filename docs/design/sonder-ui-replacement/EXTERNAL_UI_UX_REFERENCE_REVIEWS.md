# External UI/UX reference reviews

**Status:** Design evidence, not implementation authority

**Scope:** Player- and host-facing UI/UX only. Backend design, persistence,
provider architecture, and extension architecture are out of scope.

**Sonder baseline:** `1ec696a72ad6ef0bdc7f916da9db0a91496f30ae`
(2026-08-23)

**Authority boundary:** A finding here does not change
[`INTERFACE.md`](../../guides/INTERFACE.md), the approved
[`Sonder UI Design Bible`](../sonder-ui-bible/README.md), or the supplied
reference compositions. It becomes product work only through the normal
specification and change-control path.

This record prevents two opposite mistakes: copying a neighbouring interface
because it looks polished, and dismissing a useful interaction because its
surrounding visual language does not belong in Sonder. Each reference is
reviewed against the same questions:

1. What user problem does the interaction solve?
2. Does Sonder already solve it?
3. Can the interaction be adapted without changing Sonder's approved
   information architecture or visual language?
4. Is the interaction accessible, discoverable, and stable on small screens?
5. Does the source licence permit implementation reuse, or only independent
   implementation of the idea?

## Dispositions

| Disposition | Meaning |
|---|---|
| **Adapt** | The user problem and interaction shape are valuable, but Sonder should implement them in its own visual system and runtime contracts. |
| **Already present** | The reference corroborates an existing Sonder contract. It may sharpen qualification, but does not justify a new feature. |
| **Defer** | Potentially useful, but dependent on missing evidence, reliable data, or a clearer user need. |
| **Reject** | Conflicts with Sonder's information hierarchy, accessibility rules, visual direction, or product boundaries. |

---

## AstraProjecta

| | |
|---|---|
| **Source** | [RivelleDays/SillyTavern-AstraProjecta](https://github.com/RivelleDays/SillyTavern-AstraProjecta) |
| **Snapshot reviewed** | [`e7ab01f8e61008ea59da695cc5ab8e33824899e2`](https://github.com/RivelleDays/SillyTavern-AstraProjecta/tree/e7ab01f8e61008ea59da695cc5ab8e33824899e2), reviewed 2026-08-23 |
| **Licence** | [AGPL-3.0](https://github.com/RivelleDays/SillyTavern-AstraProjecta/blob/e7ab01f8e61008ea59da695cc5ab8e33824899e2/LICENSE.txt). No source, markup, styles, or assets are candidates for incorporation into MIT-licensed Sonder. The interaction ideas below require independent implementation. |
| **Evidence reviewed** | Project README and preview images; the search/replace, context-usage, stable-generation-actions, and long-press change records; current Sonder Play, responsive, and anti-pattern contracts; current Sonder Play screenshots at desktop and phone widths. |
| **Confidence limit** | Repository evidence and static screenshots were reviewed. No authenticated live-host session was treated as proof. |

### Findings worth carrying forward

| ID | Finding | Disposition | Priority | Sonder adaptation |
|---|---|---|---|---|
| `ASTRA-UX-01` | **Find in Story as a temporary transcript task mode.** Astra's mobile search work gives the task the top bar and lower action region instead of squeezing another permanent control into the chat shell. It preserves match state and makes the current result visible in context. | **Adapt** | High | Add read-only transcript search before considering editing. On mobile, temporarily repurpose the Play header and composer region for query, previous/next result, match count, and an explicit exit. Preserve scroll position when entering and leaving. Do not import global replace: Sonder narration is coupled to versioned story and committed state, so text replacement is not a harmless chat-log operation. Evidence: [PR 13](https://github.com/RivelleDays/SillyTavern-AstraProjecta/pull/13). |
| `ASTRA-UX-02` | **Revision history should be a browsable history, not a one-item stepper.** Astra's mobile revision sheet exposes the available variants, the selected state, and the action in one place. Sonder's current Versions dialog presents one version at a time behind Previous/Next controls, which hides the size and shape of the history. | **Adapt** | High | Keep Sonder's existing version ownership and activation behavior, but present the known versions as a visible ordered list with the current version marked. Use a bottom sheet on phones and a contained dialog on larger screens. Selection must remain explicit and keyboard-operable. Evidence: [revision-history preview](https://github.com/RivelleDays/SillyTavern-AstraProjecta/blob/e7ab01f8e61008ea59da695cc5ab8e33824899e2/.github/assets/preview/alpha-mobile-revision-history.png). |
| `ASTRA-UX-03` | **Generation state must not make the composer and turn actions jump.** Astra explicitly reserves the footer/action geometry through generation and the settling transition. | **Already present** | High qualification target | This reinforces the Design Bible's existing rule against state-induced layout shift and its stable composer contract. Qualify Sonder at real phone widths with the software keyboard shown: submit, streaming/generation, cancellation, completion, and error must keep the composer reachable and the transcript anchor stable. Evidence: [PR 33](https://github.com/RivelleDays/SillyTavern-AstraProjecta/pull/33). |
| `ASTRA-UX-04` | **Context and token use belong in progressive disclosure.** Astra presents usage as metric tiles plus a breakdown rather than as permanent message chrome. | **Defer** | Medium | If Sonder can expose reliable, provider-neutral usage data, add it to the existing Turn Details surface. Do not add a permanent composer ring or let approximate numbers look exact. Separate model context occupancy, current-turn input/output, and estimates with plain labels. Evidence: [PR 7](https://github.com/RivelleDays/SillyTavern-AstraProjecta/pull/7). |
| `ASTRA-UX-05` | **Mobile task modes are a reusable shell pattern.** Search demonstrates that a focused task can temporarily take over existing high-attention regions without adding a second navigation system. | **Adapt** | Supporting pattern | Reuse the same responsive staging for Find in Story and Versions: one task title, one obvious exit, stable content beneath it, and controls in thumb reach. This is a shell behavior, not permission to reproduce Astra's glass styling or icon density. |

### Deliberate rejections

| ID | Reference pattern | Decision |
|---|---|---|
| `ASTRA-REJ-01` | Per-message avatars, timestamps, token counts, and utility chrome | **Reject.** Sonder's primary surface is prose, not a messaging dashboard. Keep turn metadata behind Turn Details and controls behind the selected turn. |
| `ASTRA-REJ-02` | Dense icon-only composer actions | **Reject.** It raises recognition cost, weakens discoverability, and creates a button field at the most-used control. Sonder should retain a small, labeled hierarchy and accessible names. |
| `ASTRA-REJ-03` | Glass, blur, and scenic imagery under primary reading surfaces | **Reject.** It reduces prose contrast and conflicts with the Design Bible's restrained use of depth. Themes may change atmosphere without compromising the reading plane. |
| `ASTRA-REJ-04` | A second main navigation drawer beside Sonder's approved shell | **Reject.** It duplicates information architecture rather than solving a missing route. |
| `ASTRA-REJ-05` | Long-press as the only route to a message action | **Reject.** Long-press may be a shortcut only when the same action has a visible, keyboard-accessible route. Astra's own change record describes it as optional enhancement rather than the sole route: [PR 29](https://github.com/RivelleDays/SillyTavern-AstraProjecta/pull/29). |
| `ASTRA-REJ-06` | Copying source, markup, styles, or assets | **Reject.** AstraProjecta is AGPL-3.0 and Sonder is MIT. Only independently implemented interaction ideas are in scope. |

### Recommended order if these become product work

1. Specify and build read-only Find in Story.
2. Replace the one-item Versions stepper with an explicit revision list.
3. Add real-device geometry qualification for generation and software-keyboard
   transitions to the Play review gate.
4. Add Turn Details usage disclosure only after the data contract can label
   exact values and estimates honestly.

This order improves navigation and recovery before adding more metrics. None of
the four is recorded as built by this review.

---

## ChungusHub

| | |
|---|---|
| **Source** | [patcireamo/ChungusHub](https://github.com/patcireamo/ChungusHub) |
| **Snapshot reviewed** | [`5c493fe1730543edd7c362302624db6f28255ec1`](https://github.com/patcireamo/ChungusHub/tree/5c493fe1730543edd7c362302624db6f28255ec1), reviewed 2026-08-23 |
| **Licence** | [AGPL-3.0](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/LICENSE). No source, markup, styles, or assets are candidates for incorporation into MIT-licensed Sonder. The interaction ideas below require independent implementation. |
| **Evidence reviewed** | Project README; the supplied 3840×2160 desktop and 482×1048 mobile screenshots; current `ChatSearchBar`, `StoryMapView`, `Workspace`, and `WelcomeView` presentation source; the Quickstart and SillyTavern migration guides; current Sonder no-story, Play, Library, responsive-shell, and contextual-tool evidence. |
| **Confidence limit** | Public repository evidence and supplied renders were reviewed. The packaged app was not installed, and no live pointer, software-keyboard, screen-reader, or long-story performance session was treated as proven. |

### Findings worth carrying forward

| ID | Finding | Disposition | Priority | Sonder adaptation |
|---|---|---|---|---|
| `CHUNGUS-UX-01` | **Search keeps active-path results and off-path results conceptually separate.** ChungusHub searches story text rather than message chrome, reaches behind the rendered transcript window, cycles matches only on the current branch, and lists alternate-branch hits separately. Opening a different branch is an explicit selection rather than a side effect of Next. | **Adapt** | Highest | This sharpens `ASTRA-UX-01`. Sonder's first release should search the complete active transcript while excluding controls and metadata. If results are later exposed from another narration variant, frame, or other non-active context, group them under a clearly named secondary section and require an explicit context switch. Never make Next silently change the story context. Keep Enter/Shift+Enter navigation, an announced match count, and Escape that closes search without losing the reader's location. Evidence: [`ChatSearchBar.svelte`](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/src/lib/components/chat/ChatSearchBar.svelte). |
| `CHUNGUS-UX-02` | **The empty chat surface is also a useful resume surface.** ChungusHub gives New chat one primary action, keeps Chats and Library secondary, and presents up to three recent resumable stories with artwork, last activity, and current persona before expanding to the full list. Sonder currently exposes recent story titles in its no-story Play state, but gives the reader little evidence for choosing between them. | **Adapt** | High | Improve Sonder's existing no-story Play composition instead of inventing a welcome dashboard. Keep the current Play heading and approved shell, but render recent stories as compact resume rows with a useful secondary fact such as last played time and current location or turn. Provide one `All stories`/Library route. Do not import ChungusHub's brand hero, community links, or duplicate global shortcuts. Evidence: [`WelcomeView.svelte`](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/src/lib/components/layout/WelcomeView.svelte) and [mobile welcome render](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/images/screenshots/mobile_welcome.png). |
| `CHUNGUS-UX-03` | **A branch map can turn revision history into spatial navigation.** ChungusHub distinguishes the current path, a separately chosen canon path, forks, and labeled branches; supports search, comparison, overview/minimap, explicit jump, and a desktop inspector/mobile sheet. Its keyboard model traverses parent, child, and sibling nodes rather than treating the graph as pointer-only decoration. | **Defer** | Strategic | Do not draw a tree over data that is not a tree. If Sonder later owns durable branching story history, use these UI principles in a Sonder-specific specification: visually distinct current and chosen paths, named branches, explicit jump, comparison as a focused task, detail only above a readable zoom, and a mobile sheet instead of a tiny floating inspector. Test the graph without relying on `role="application"` as a shortcut for accessibility. Current narration variants and frames must not be conflated merely to make a map possible. Evidence: [`StoryMapView.svelte`](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/src/lib/components/storymap/StoryMapView.svelte). |
| `CHUNGUS-UX-04` | **Supporting work can preserve the user's place in the primary workspace.** On wide displays, ChungusHub docks Settings and Library outside the centered chat column; editors open over the center while the originating list keeps its place. On narrow screens the same destinations stage into full workspace overlays. | **Already present** | Qualification target | Sonder already owns the better-fitting version of this idea: a stable Play center, a lifecycle-owned contextual rail that can pin and resize, focused authoring workspaces, and staged compact presentation with return-state restoration. Use ChungusHub as corroboration for preserving scroll, selection, draft, and focus when opening deeper work. Do not add independent global Settings and Library docks on both sides of Play; that would turn the approved shell into the generic three-pane console the replacement explicitly rejects. Evidence: [`Workspace.svelte`](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/src/lib/components/layout/Workspace.svelte) and [desktop workspace render](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/images/screenshots/desktop_settings_and_library.png). |
| `CHUNGUS-UX-05` | **Bulk import earns trust through before-and-after receipts.** ChungusHub describes a pre-write count, a post-import summary, named failed files, missing-character follow-up, and an incremental rerun that does not duplicate prior work. | **Defer** | Medium | Sonder's current Library imports individual supported records and already retains recoverable drafts and named errors. If it gains a profile- or folder-scale migration, require a preflight inventory, explicit unsupported/missing dependencies, a final imported/skipped/failed receipt, and a safe rerun path. Do not expose provenance bookkeeping as a choice the player must understand. Evidence: [Coming from SillyTavern](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/docs/coming-from-sillytavern.mdx). |

### Deliberate rejections

| ID | Reference pattern | Decision |
|---|---|---|
| `CHUNGUS-REJ-01` | Message bubbles or portrait cards as Sonder's default transcript | **Reject.** The supplied desktop and phone renders devote substantial width and vertical space to avatars, metadata, card boundaries, and per-message toolbars. That is coherent for a configurable chat frontend but weaker for Sonder's prose-first reading surface. Keep the speaker identity and turn actions available without framing every turn as a social-message object. Evidence: [desktop Bubbles](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/images/screenshots/desktop_chat_bubbles.png), [desktop Portraits](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/images/screenshots/desktop_chat_portraits.png), and [mobile chat](https://github.com/patcireamo/ChungusHub/blob/5c493fe1730543edd7c362302624db6f28255ec1/images/screenshots/mobile_chat.png). |
| `CHUNGUS-REJ-02` | Icon-only global navigation across the top of the phone | **Reject.** The supplied mobile renders make primary destinations small, unlabeled symbols at the far edge of the thumb path. Sonder's persistent three-item bottom navigation is more discoverable and reachable. |
| `CHUNGUS-REJ-03` | Workspace-wide background, blur, and particle effects over or behind every panel | **Reject as a default composition.** Sonder already separates scene effects from interface surfaces. Keep effects optional, failure-isolated, reduced-motion aware, and out of the prose plane; never let a theme make primary content translucent merely to show an effect. |
| `CHUNGUS-REJ-04` | Simultaneously docked global Settings and Library around Play | **Reject.** It preserves context on an exceptionally wide display but makes three peer destinations visible at once and compresses the reading workspace. Sonder's one navigation rail plus one contextual region has clearer ownership. |
| `CHUNGUS-REJ-05` | Copying source, markup, styles, or assets | **Reject.** ChungusHub is AGPL-3.0 and Sonder is MIT. Only independently implemented interaction ideas are in scope. |

### Recommended order if these become product work

1. Combine Astra's focused mobile task staging with ChungusHub's branch-aware
   semantics in the Find in Story specification.
2. Improve the existing no-story Play state with informative recent-story
   resume rows.
3. Preserve the current shell and use ChungusHub only as additional evidence
   for contextual-workspace state restoration.
4. Revisit a story map only after Sonder has an authoritative durable branch
   model and a measured navigation problem that a graph solves better than a
   list.
5. Apply import receipts only when a genuinely bulk import workflow exists.

The first two are actionable UI opportunities. The remaining findings are
qualification rules or capability-dependent designs, not present-tense feature
commitments.
