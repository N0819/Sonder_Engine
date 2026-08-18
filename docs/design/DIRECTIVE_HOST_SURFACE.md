# Hosting a Directive-class extension — design note

Status: **all three named blockers are built, and so are the five gaps the
report that followed them named** (§9). Written 2026-08-17 against
[Directive](https://github.com/MentallyQuill/Directive) at `0.1.0-pre-alpha.1`
and Sonder `main` at 4f33b17; §§3–5 were a study, and the sections marked
**Built** below landed in the same branch. §9 answers `DIRECTIVE_GAP_REPORT.md`,
written against 9.2 by Directive's author after building on this tree.

| Blocker | State |
|---|---|
| §3 narration context | **Built** — `api.on_narration_payload`, `api.narration_context`; `tests/test_extension_narration.py` |
| §4 UI mount points | **Built** — `registerTopBarButton`, `registerView`, `registerComposerControl`, `openView`/`closeView`; `tests/test_extension_ui_surface.py` |
| §5 ES modules | **Built** — `capabilities.ui.module`; `tests/test_extension_modules.py` |
| §3 prose author | Not built, and deliberately so — see the section |
| §6 secondary gaps | Not built; registered in [`UNBUILT.md`](../UNBUILT.md) §6.2 |
| §9 the five gap-report gaps | **Built** — `api.director_context`/`on_director_payload`, `api.story_view`, `api.player_view`, `api.provision_story`, and hard mode (`PlayerAuthorityMode`, enforced) |

What an author needs is [`docs/guides/EXTENSIONS.md`](../guides/EXTENSIONS.md)
§4, §7.1 and §7.5. This file keeps the measurement and the reasoning.

This file is the **argument** for widening the extension surface until a
total-conversion extension is a supported thing rather than a tolerated one.
What the extension system does today is
[`docs/guides/EXTENSIONS.md`](../guides/EXTENSIONS.md); if this note and the
guide disagree, the guide is right. What is unbuilt is
[`UNBUILT.md`](../UNBUILT.md) §6.2, which already carries three of the gaps
below.

The occasion: Directive's author wants ST-level freedom — "I can put buttons
anywhere, and change functionality anywhere." Two blockers were named in advance
(narrator-context injection, and an app-level UI surface). Both are real. A
third was not named and is the one that stops a build on day one.

---

## 1. The measurement that changes the estimate

The prior reading was "a rewrite into Python." That is true of at most one of
three possible integration postures, and it is not the one Directive is shaped
for.

**Directive is already host-abstracted.** It ships an explicit boundary at
`src/hosts/host-contract.mjs` (262 lines), a test-only `hosts/fake/`, and
`hosts/sillytavern/` as the production adapter. Its own README states the split:
the shared runtime owns campaign state, mission validation, narration context and
player-safe projections; a host adapter supplies "chat events, accepted-message
identity, generation, exact logical storage, UI mounting, and host settings."

Measured:

| Layer | LOC (js/mjs) | Portable? |
|---|---|---|
| `src/hosts/` | 7,347 | **no** — this is the part you rewrite |
| everything else in `src/` | 26,997 | yes, host-agnostic by construction |
| **total** | **34,344** | 156 files |

So the port is a `src/hosts/sonder/` adapter — call it 2–3k LOC, since 2,461 of
ST's 7,347 are a chat adapter absorbing ST-specific chat identity that Sonder
models differently — **not** a 27k-line transliteration of a campaign engine into
Python. That is a materially different project, and the difference is Directive's
own architecture, not anything Sonder did.

The contract also tells us precisely what a `sonder` host must supply. The ST
host declares these capability families true: `storage` (json, binary, verify,
delete, userScoped), `generation` (currentChatModel, quiet, raw, batch,
observeMainGeneration, connectionProfiles, structuredOutput), `prompt` (install,
update, clear, rebuild, lifecycle, scopedToChat), `chat` (identity, create, bind,
open, clone, postAssistant, assistantSwipes, message observe/edit/delete,
metadata), `ui` (**panelMount only**), `presets` (narrationContext,
chatCompletion, narrationLifecycle, install), `lifecycle` (enable, disable).

Note the `ui` row. Even on SillyTavern, Directive gets `panelMount` and nothing
else through the contract. Every other piece of its interface — the launcher
button, the expanded shell, the notification centre — is built by querying ST's
DOM by id with a fallback chain (`src/hosts/sillytavern/directive-launcher-button.js`
tries `#extensionsMenuButton`, then `#leftSendForm`, then `document.body`). ST's
famous freedom is *the absence of a sandbox*, not a rich mount API. Worth knowing
before we try to out-design it.

## 2. Three postures, and why the blockers differ per posture

**A — Overlay.** Directive's engine runs browser-side; Sonder is a shell that
supplies storage, generation and a mount point. Closest to what it does in ST,
smallest port. But Sonder's pipeline is bypassed, and Sonder is then a worse ST.

**B — Absorbed.** Directive's engine moves server-side as a Python extension; the
pipeline narrates. This is the "rewrite into Python" reading. It is the most
Sonder-native and by far the most expensive, and it throws away 27k lines of
tested JS.

**C — Hybrid, and the one to build for.** Directive's engine and UI stay JS in
the browser and keep owning campaign state; a thin Python half persists that
state and feeds the narrator. Sonder's pipeline still narrates the beat.

C is not a compromise — it is what Directive already does on ST. It does not
drive generation itself: it maintains one keyed context block via
`setExtensionPrompt` and lets the host's own narration run with that block in
scope. Map `setExtensionPrompt` onto a Sonder narrator-context seam and the
architecture lines up almost exactly.

That mapping is why blocker #1 is the linchpin rather than one item of three.

## 3. Blocker 1 — nothing an extension knows can reach the prose

**Built for the narrator; not built for the Director's prose author.** The
diagnosis below is as written; what shipped is at the end of the section.

Real, and already registered. [`UNBUILT.md`](../UNBUILT.md) §6.2:

> **An extension specialist cannot reach the prose author.** `PROSE_AUTHOR_SHEET`
> and `test_every_delegated_block_has_exactly_one_owner` are in-tree, so a
> registered family writes its channel to the merged `state_diff` and nothing
> narrates it.

The guide says the same to an author's face (§4): "Nothing narrates it… a change
you record reaches the ledger and not the prose unless you put it there." There
is no `prompts` runtime seam either — `manifest["prompts"]` and
`manifest["prompt_presets"]` are read at `extension_runtime/__init__.py:167` for
**trust-class computation only** and are never consulted again.

So today an extension can add a Director specialist, own a namespaced
`state_diff` channel, and write per-story state — and the reader never sees any
of it unless the extension renders its own panel. For a campaign layer whose
entire job is to colour the narration, that is fatal.

**Where the seam goes.** The precedent is exact and one function long.
`agents/character.py:3216` calls `_extension_character_payload`, which calls
`extension_runtime.dispatch_character_payload` (`__init__.py:748`), registered
through `api.on_character_payload` (`api.py:637`). The narrator has the identical
shape available: `agents/narration.py:767` `_generate_narration` opens with
`call_payload = dict(payload)` at line 769, immediately before `_agent_json`.
One dispatch call there covers the narrator. `narrator_extra` builds its own
payload at `narration.py:1101` and needs the same treatment or extra players
silently diverge from the main reader.

**Two surfaces, not one.** Offer both:

- `api.on_narration_payload(fn)` — the raw hook, mirroring
  `on_character_payload`: unrestricted, and paying for that with **attribution**,
  every top-level key you changed recorded against your id on the durable turn.
- `api.narration_context` — a keyed, chat-scoped, revision-tracked text block,
  which is the ergonomic 90% case and is exactly what `setExtensionPrompt` is.
  Directive's `prompt-adapter.mjs` already implements install/update/clear/
  rebuild/syncForChat/inspect against a single key with a content hash and a
  refusal to install into an unbound chat; that adapter becomes ~30 lines
  against this.

**Two things to get right, neither of them the firewall.** First, the narrator
runs a deterministic fidelity checker (`_check_narrator_fidelity`) over event
order, position facts, room names and portal states; injected context that
asserts world facts will fight it, and the failure will look like a model
problem. The block wants to be scoped as *setting and standing situation*, not
world state, and that wants saying in the API's own words. Second, the Director's
prose author is a **separate** unbuilt problem: its sheet is assembled from
in-tree `PROSE_DUTY_CHUNKS` (`prompts.py:71`, consumed at `agents/director.py:5499`
and `:7105`) with a one-owner test across it. Closing that means a prose-chunk
registry that extends the one-owner test across the boundary. The narrator seam
does **not** require it, and shipping the narrator seam first is the right order.

## 4. Blocker 2 — the UI surface is two mount points wide

**Built: it is now five.** The diagnosis below is as written.

Also real, but the diagnosis wants correcting. This is not a *permission* problem.
The guide's §8 is unambiguous and already says what Nathan wants said:

> Your JavaScript runs same-origin in the host document with the session cookie:
> no iframe, no CSP, no sandbox. You can replace `document.body`, wrap
> `renderChat`, and call every host API.

Full stylesheet replacement is explicitly supported, not tolerated. So the
ceiling is already ST's.

The gap is that **the declared surface is two entries wide** —
`registerSidebarTab` and `registerStepRenderer`, plus five read-only turn events
(`static/js/extensions.js`). Everything Directive needs beyond a sidebar tab must
be done by reaching into the host DOM: a launcher button beside `#input`, a
full-window shell over `#main`, a notification centre, a settings section, a
composer adornment, a top-bar button next to the host's own in `#topactions`.

That is permitted and it is what Directive does on ST. But off-contract has a
price the guide already names: `Sonder._safe`'s three-strikes retirement only
counts throws routed through the registry, and `Sonder._unload` "cannot undo side
effects, only registrations and the two injected elements." An extension that
builds its interface by monkeypatching is outside containment *and* cannot be
cleanly disabled. That is exactly the cooled-off feeling described for
panel-only hosts, arriving by the opposite route: not "I am not allowed" but
"nothing I build is held by the host."

**So the work is contract, not capability.** Additions worth having, each cheap,
each an entry in one registry with `_unregister` teardown and `_safe` wrapping —
the same shape the two existing ones already have:

| Call | Need it serves |
|---|---|
| `registerTopBarButton({id, icon, title, onClick})` | the launcher, next to `#topactions` |
| `registerView({id, label, render})` | a full-window surface over `#main` — Directive's five screens |
| `registerComposerControl({id, render})` | a control beside `#input` |
| `registerSettingsSection({id, label, render})` | settings inside the host's menu instead of a bolted-on modal |
| `notify(payload)` | a notification centre; `toast` exists and is not one |
| `registerMenuItem`, `registerMessageAction` | per-message affordances |

None of that is novel engineering. Its value is that a host-owned registry can
retire a broken panel, redraw it on theme change, and take it away on disable —
which the DOM-injection route cannot. Ship the registries *and* keep the
no-sandbox posture; the point is to make the supported path the attractive one,
not to close the other.

Frontend note: `#app` is a fixed two-pane shell in `static/index.html` and
`renderSide`/`renderChat` are globals. A `registerView` that takes over `#main`
needs a host-owned routing notion the app does not have yet (`S.tab` handles the
sidebar only). That is the one piece of this section with real design in it.

## 5. Blocker 3 — the one nobody named: no ES modules

**Built.** The diagnosis below is as written.

**This stopped a build on day one and neither party had hit it yet.**

Directive is `"type": "module"` with 156 `.js`/`.mjs` files and ES `import`
between them. Sonder serves extension UI as **one concatenated classic script**:
`extension_runtime/__init__.py:1040` joins every enabled extension's entry, and
`_wrap_ui` (`:975`) wraps each in `(function () { … })()`. `Sonder._load` injects
a `<script>` with no `type`. An `import` statement in a classic script is a
SyntaxError — and per the guide, "a top-level `ReferenceError` in your file takes
down every extension after it."

Two ways out:

- **Directive bundles.** esbuild/rollup to one classic IIFE. A build step, no
  host change, and probably what happens first regardless.
- **Sonder serves modules.** Let a manifest declare `ui: {"module": "..."}` and
  serve that entry from `/api/extensions/{id}/ui.js` as its own
  `<script type="module">`, with relative imports resolving under
  `/api/extensions/{id}/asset/`. `Sonder._load` already injects per-extension
  script elements, so the hot-load path barely changes.

The second is the better host fix and pays for itself past Directive: a module
per extension also ends the "one extension's SyntaxError kills the bundle"
hazard the wrapper works around today. The `_begin`/`_end` attribution trick does
not survive module load ordering, so a module entry would take its id explicitly
(`export function register(sonder)`, called with a bound, id-stamped facade) —
which is a better design anyway, and mirrors the Python half's `register(api)`.

## 6. Secondary gaps

Worth listing so a build does not discover them one at a time.

- **No extension-declared model lane.** `api.llm_json`/`llm_text` take
  `role=`, and roles come from `providers.ROLES` — a fixed host list. Directive
  configures its own two lanes with their own models and samplers. Either allow
  an extension-declared role that appears in the host's model settings, or accept
  that Directive's lanes collapse onto host roles.
- **No document storage.** Directive's storage adapter is JSON documents at
  logical paths with `list`/`delete`/`verify`; Sonder offers four namespaced KV
  homes. The KV can back it, but `listJsonFiles`/`verifyJsonFiles` have no
  analogue, and Directive's Settings screen has a storage-check path that depends
  on them.
- **`ext:<id>` world state is not frame-scoped** (UNBUILT §6.2) — shared across
  eras. A campaign layer probably wants per-frame.
- **Chat lifecycle from the browser.** `createOrBindCampaignChat`, `clone`,
  `open`, `postAssistantMessage`, `appendAssistantMessageSwipe`. Sonder has all
  of these as host HTTP routes reachable via `Sonder.api(...)`, but they are not
  a declared extension contract, so they are refactor-fragile. Directive's swipe
  model ("replies are drafts until you send the next message") also needs
  checking against Sonder's variants/reroll before either is assumed to fit.
- **No `on_admission`/`on_view`** (UNBUILT §6.2) — designed alongside
  `on_character_payload`, not built. Not needed for Directive; needed by the next
  extension that wants to alter what perception admits.

## 7. What is already fine

Stated so nobody rebuilds it. Install from git repo, zip or folder with
zip-slip/symlink refusal, size ceilings, atomic `os.replace`, provenance and
sha256 recorded; enable/disable/remove live on the server and hot in the browser;
update via `ls-remote` without downloading; per-item load isolation so one bad
extension cannot fail `import app`; computed trust classes with a consent dialog;
pipeline stages at named anchors; `on_step`, `on_turn_committed`, in-transaction
commit domains; a seventh Director specialist with namespaced channels; four
state homes that ride checkpoints, archives and branches for free; extension-owned
HTTP routes; full CSS replacement; three-strikes containment.

That is a real extension system. The gaps above are a surface being two mount
points and one seam short of a total conversion, not a system that needs
rethinking.

**And the firewall question is already settled in-tree, correctly.** The guide's
§8 opens "The information firewall is for MINDS, not for developers", and
`EXTENSIONS_DESIGN.md` §1 records the earlier, narrower API as a ruling that was
*wrong* — it "conflated reading a mind with writing to one." Anyone who reads
`AGENTS.md` § Information boundaries as a constraint on extension authors is
reading it against its own canonical statement. No document change is needed
here; it is worth knowing the argument was had and won before it is had again.

## 8. What shipped, and what a port does next

All three named blockers, in the order §§3–5 argued for:

1. **ES module loading** — `capabilities.ui.module`, served from `/asset/` so
   relative imports resolve, loaded by dynamic `import()` and handed an
   **id-bound facade** rather than `window.Sonder`. The facade is not a
   nicety: the classic path's `_begin`/`_end` attribution is ambient state that
   does not survive an `await`, so a module's async `register` would otherwise
   attribute whatever ran during its await to itself. `_PUBLIC` is the single
   list the facade is built from, guarded by a test, so a registry added later
   cannot silently work for classic extensions and be missing for module ones.
2. **The narration seam** — `api.narration_context(chat_id)` for standing
   context (one block per extension per story, replaced not appended, revision
   stable across identical re-installs, 8000-character ceiling because the cost
   is per beat) and `api.on_narration_payload` for the general case. Both
   attributed onto the turn beside the character-routing notes. Applied **once
   per beat** rather than once per attempt, so the narrator's fidelity and craft
   retries reuse the hooked payload — a hook re-run per attempt would let a
   correction pass narrate against a frame the first pass never saw.
3. **Three UI mount points** — `registerTopBarButton`, `registerView` (a
   full-window surface over the transcript, host-owned open state) and
   `registerComposerControl`. Each cleared by `_unregister`, so a disable takes
   the interface back down; retiring the owner of the *open* view returns the
   reader to their story rather than stranding them in a dead application.

The prose-author chunk registry (§3) is deliberately not among them: it is a
harder problem with a one-owner invariant across it, and the narrator seam
delivers the reader-visible result without touching it.

**What a port does next.** Write `src/hosts/sonder/` against
`host-contract.mjs`. `prompt` maps onto `api.narration_context` — install /
update / clear / rebuild / inspect are that block's `set` / `set` / `clear` /
`set` / `get`, and the content hash and revision it already expects are stored
for it. `ui.mount` maps onto `registerView`. `events` maps onto the five
`turn:*` stream events. `storage` and `chat` are the two that will bite, and
both are in §6 rather than in the tree.

---

## 9. The gap report, and the five that answered it

Written 2026-08-17 against alpha 9.2 by Directive's author, after reading this
tree rather than guessing at it (`DIRECTIVE_GAP_REPORT.md`). Its framing is
right and worth adopting: **replacement-first, not migration**. Sonder keeps
world state, time, minds, memory, perception, model access, narration, commits,
checkpoints, branches and extension lifecycle; Directive becomes a campaign
layer with authored missions, deterministic mission rules, player-safe views and
its own interface. Nothing about that requires Sonder to learn what a starship
is.

Five gaps were named. All five are now built. Two of the report's premises were
wrong in ways worth recording, because both errors are the same error.

### What the report got right

Four of the five were straightforwardly absent, and each is a real hole rather
than a preference:

| Gap | Built as |
|---|---|
| Director context injection | `api.director_context` (per phase) + `api.on_director_payload` |
| Read-only canonical story view | `story_view.py` → `api.story_view`, `GET /api/chats/{id}/story_view` |
| Player-safe projection | `api.player_view`, `api.viewers` |
| Campaign provisioning | `api.provision_story` over the chat-archive importer |

The ordering it recommended was also right, and for the reason it gave: player
authority first, because every later integration test is otherwise validating
against canon that may contain invented player acts.

### Gap 5's premise was wrong, and instructively

The report says Sonder "declares player-authority modes but does not enforce
them", citing this repository's own unbuilt register. The register is accurate
about the **enum** and it is not the whole picture, because the enforcement was
built under other names and never collected under that one:

- `_check_player_act_authority` — physical acts a resolve gives the player that
  they did not declare;
- `_check_player_interiority_authority` — what the resolve says the player
  FEELS;
- `_check_character_act_authority`, `_check_character_speech_authority`,
  `_check_prose_quote_authority` — the same boundary from the cast's side;
- all five behind ONE correction retry in `director_resolve`, kept only if it
  reduces the total violation count — which is precisely the
  "validator-and-retry, prompt text alone is not acceptable" mechanism the
  report asks for;
- `_scrub_undeclared_player_speech` at the perception layer, and
  `_check_player_interiority_prose` + `_check_player_person` among the
  narrator's enforceable fidelity prefixes.

So the engine already refused to invent player conduct. What it had no switch
for was the **other** direction: Sonder's default is `world_author`, where a
player's asserted effect is *non-rejectable* — `_player_claim_findings` raises a
contract violation when a resolve marks one rejected. Directive wants
`actor_only`, which is that rule inverted. Hard mode is therefore not "add
enforcement to an unenforced engine"; it is "let the story choose which
direction the existing enforcement points". Built as §2.4 of `UNBUILT.md`
specified it, default unchanged.

### Gap 2's premise was the same error, from the other side

The report is careful to frame the canonical facade as needing to avoid "arbitrary
minds" and "hidden reasoning", and treats objective truth as something to be
justified. It does not need justifying. The firewall constrains what reaches a
fictional MIND; a campaign layer is not one, any more than the pipeline
inspector or `make map` is. That ruling predates the report
(`EXTENSIONS_DESIGN.md` §1) and is why `story_view` is simply canonical.

The instructive part is that both misreadings run the same way: an outside
reader sees "information firewall" and infers a general restriction on
observation. It is worth saying plainly in the guide, and §8 of
`docs/guides/EXTENSIONS.md` now does.

### What was deliberately not built from it

- **A declarative campaign-package format.** The report asks for "a declarative
  package or a sequence of supported builder calls". It gets the chat archive,
  which is already atomic, validated, id-remapping, and exercised on every
  branch and every restore. A second importer would be a second copy of the bugs
  the first one has already had. Directive-specific package translation stays
  inside Directive, exactly as the report proposes.
- **A prompt clause telling the Director to honour extension context.** The
  block rides in `payload["extension_context"]`, attributed, alongside every
  other extension's — the same shape the narration seam ships. Naming it in the
  prompt as authoritative would violate the report's own safeguard that an
  extension must not be able to impersonate an engine-owned instruction.
- **§6's secondary list**, unchanged: notification surface, settings mount
  point, extension-declared model lanes, document storage, the chat lifecycle as
  a declared contract. The report agrees none of them blocks a first
  integration.

### The vertical slice

The report's §5 defines "the gaps are closed" as ten steps ending in a
checkpointed, branchable campaign. Steps 1–4 and 7–10 are now reachable through
public API only. What is not yet proven is the whole thing running end to end,
because that needs a reference campaign to exist — the report's step 5, and the
right next piece of work on this side.
