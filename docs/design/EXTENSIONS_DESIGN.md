# Extension System — design note

Status: **built and shipping in 9.0.** The loader, the facade, the plan-splice
registry, per-story/per-character/settings state, character reads, the
`window.Sonder` registries, install/enable/disable/remove, and the
`cohesion-demo` reference extension shipped first; a second batch added served
stylesheets, client-side hot-load, extension-owned routes, in-transaction commit
domains, the attributed character-payload routing hook, a model-call facade and a
Director-specialist registry (§7a). All in the tree: `extension_runtime/`,
`extensions/`, `static/js/extensions.js`, `tests/test_extensions.py`,
`tests/test_extension_seams.py`, `tests/test_extension_install.py`.

This file is the **argument**. What the system *does*, field by field, is
[`docs/guides/EXTENSIONS.md`](../guides/EXTENSIONS.md); if the two disagree, the
guide is right. What remains unbuilt is [`UNBUILT.md`](../UNBUILT.md) §6.2.

The note was rewritten when the system was built. The version it replaces was an
exploratory ladder of four tiers whose central safety claim did not survive
contact — §2 records why, because the reasoning is the part worth keeping.

---

## 1. The ruling that reshaped the design

The first plan narrowed the developer API "for firewall reasons": stages would
receive scoped views because a broader surface could leak; extension output could
not reach a character payload; the recommended ship was a declarative,
data-only tier precisely *because* it could not breach the boundary.

That was wrong, and it was wrong in a way worth naming because it is easy to
repeat. It conflated **reading** a mind with **writing** to one.

> **The firewall is for MINDS, not for developers or tooling.** It constrains
> what reaches a fictional mind. It says nothing about what the engine, its
> instruments, or a third party may OBSERVE — reading a mind puts nothing in
> anyone's head. The only place a breach can occur is the WRITE side.
>
> — [`AGENTS.md`](../../AGENTS.md) § Information boundaries, now the canonical
> statement.

The engine already reads every mind at once, in four places, correctly: the
pipeline drawer, persisted traces, `chat_archive`, `pipeline_trace`. An API
narrowed on the read side protects nothing and costs real capability. The
owner's ruling, adopted as the design's stance:

**Developers get full access, and maintaining the epistemic firewall is theirs.
An extension that breaks it is a poorly designed extension** — the same judgment
the engine passes on a leaky core stage, applied to third-party code.

It is also the only honest position available. A `code`-class extension runs
in-process; it can reach `PipelineContext` through Python introspection no matter
what the facade withholds. Read-gating was never enforcement, only ergonomics.
Saying so converts a loophole into a documented surface.

Where responsibility transfers, stated so the developer can discharge it: Sonder's
firewall guarantee describes **Sonder's** pipeline. An extension that alters
admission, view composition, payload contents or a character's decision seam is
now the author of that part of the information model, and the guarantee is theirs
to make. An extension may contradict `Design.md` outright — omniscient characters,
collapsed layers — and that produces at worst a poorly made extension, never an
engine failure.

### 1.1 Facts versus manner, dissolved

The original open question was whether an extension might inject *facts* into a
character's prompt or only *manner*. Under the ruling it dissolves: both are
permitted, and the developer owns the result. What survives is **craft guidance,
not a rail**:

Text cannot be mechanically classified as fact versus manner, so nothing in the
engine will ever catch "the warp core is failing" appended to a mind that never
heard the klaxon. The objective route — make it true in the world, let
deterministic perception distribute it — stays the recommended pattern, but not
for safety. It is better craft. It produces dramatic irony, rumor lag and false
belief for free, because the gap between truth and each mind stays real. An
extension that pastes truth into heads flattens its own story. *That* is the
sense in which a firewall-breaking extension is poorly designed rather than
forbidden.

---

## 2. Why the tier ladder was abandoned

The replaced note proposed four tiers and recommended shipping Tier 0 (pure data
packs) plus Tier 1 (declarative advisor stages) first, on the argument that a
declarative stage's inputs come from an engine-controlled whitelist and so
"cannot breach the firewall by construction."

Three things killed it:

1. **The safety was the point, and the safety was illusory.** The ladder's rungs
   were ordered by how much they *could* breach. Once §1 settled that breaching is
   the developer's business, the ordering had no load left to bear.
2. **A declarative tier is not the cheap rung.** The generic handler, the scope
   whitelist, the prompt/schema drift lint and the payload assembler are most of
   the work of the code tier, for a fraction of its power.
3. **Nobody wanted it.** The motivating extension (a Star Trek system for another
   engine's community) needs custom UI, custom themes, character targeting and its
   own model calls on day one. Shipping a rung it could not stand on would have
   proved nothing.

So the code tier shipped first. `data` and `prompt` survive not as rungs of a
ladder but as **computed trust classes** — a label on the consent dialog,
derived from what an extension can actually do rather than from what it claims.
The declarative advisor stage remains genuinely useful for authors who write no
code and is registered as unbuilt, not as a prerequisite.

---

## 3. What the API shape is for, since it is not a wall

Every narrowing that survived is an **accident-preventer**, and each one is named
after the accident:

- A stage receives `StepView`, not `PipelineContext` — so you do not move a fact
  between two minds by *reflex*, because the object you were handed did not
  contain the other mind.
- `on_step` receives the saved key and content, never the context — so a step
  observer cannot quietly become a payload channel.
- Per-turn writes are gated to `on_turn_committed` — so an extension's write is
  not the one thing left standing when a domain failure rolls the turn back. The
  ghost-state failure is real and specific: a mid-pipeline write survives the
  rollback that undid everything it was computed from, and the rerun then replays
  against state that never went away. `set_now()` is the named escape hatch; an
  extension that wants it has to say so.
- Everything durable is namespaced `ext:<id>` — so four homes (world KV, char
  state, settings, step rows) inherit checkpoints, archives and branches
  **wholesale**, and no extension has to walk `DATABASE.md`'s schema checklist.

None of these stop a determined developer, and none are advertised as doing so.
They are the shape that makes the correct thing the *default* thing.

---

## 4. The plan splice, and why it must be pure

`register_step` always covered the handler half of adding a stage. Plan placement
was the half it punted on, and that omission is the entire reason a third party
had to edit `agents/runtime.py` to add a stage. `apply_plan_splices` closes it.

Two properties are load-bearing:

**Pure function of durable settings plus manifests.** `resume_key_for_turn` and
every `from_key` path rebuild the plan from stored step content. A splice that
varied with anything not persisted would make the recomputed plan differ from the
one that ran, and resume would break in a way that looks like data corruption.

**Silent when it cannot apply.** An unknown anchor, or an anchor naming a core
step this turn does not run, means the stage is not planned this turn — not an
error, and above all not bolted onto a nearby position. Relocating it would make
the plan differ between the run and the recompute, which is the same failure by
another route.

The anchor vocabulary is core step keys only. `character:*` is refused because
`_run_pipeline` detects the parallel character group by scanning for consecutive
`character:` keys, so a splice inside it would silently serialize the whole cast.
`ext:*` is refused because ordering would then depend on registration order,
which is not a durable fact.

---

## 5. Trust, phased

**Phase 1 — what ships.** Install from a local directory or an `http(s)` zip.
Nothing reviews what arrives. Consent is taken in the browser at the enable
moment, where the trust class is stated plainly, because a warning on a page
nobody reads is not consent.

In-process Python sandboxing (RestrictedPython, stripped builtins) is not a
security boundary and this project does not claim one. Same for the browser half:
extension JS is same-origin with the session cookie, and an `<iframe sandbox>`
would buy real containment at the cost of the `el()`/`modal()` integration that
makes writing a panel pleasant. The honest posture is Obsidian's and VS Code's —
**trusted code behind an explicit consent screen**, said out loud.

What the install path *does* owe the host, and does deliver, is narrower and
achievable: a malformed or hostile **archive** cannot damage the install before
consent is ever reached. Zip-slip and symlink members are refused before
extraction; the bundle is capped; staging is validated and then moved with
`os.replace`, so an interrupted install leaves either the old extension or none.
(That last one is not theoretical — a non-atomic checkpoint write in the
translation tool corrupted itself on interrupt and could only be recovered by
discarding paid work.)

**Phase 2 — the reviewed registry.** A site of extensions reviewed case by case.
The design decision that matters *now* is that every field phase 2 needs — stable
id, version, integrity hash, provenance record — is written at install time
today. Phase 2 is therefore an addition, not a migration of everything already
installed.

**Removal keeps history.** Deleting an extension deletes its code and leaves
`world["ext:<id>"]` alone, so reinstalling picks a story back up rather than
starting it over. Orphaned state is small and inert; the alternative silently
destroys play the host may not have meant to discard.

---

## 6. What was taken from SillyTavern, and what was refused

Read from their v1.18.0 source. The refusals shaped concrete decisions here:

- **`getContext()` as a growing grab-bag over deep-importable internals.** Their
  core failure: no boundary, so every internal refactor breaks extensions, and the
  context object carries deprecated shims as scar tissue. Sonder's facade is
  closed and versioned (`ext_api`).
- **Ordering by accident** — `loading_order` integers with an alphabetical
  fallback, prompt injections merged in alphabetical key order (built-ins prefix
  keys with digits to win). Sonder uses named anchors and deterministic id
  ordering, and §4's purity law makes ordering a *correctness* property with
  tests rather than a convention.
- **Mutation-by-reference event payloads.** Handlers mutating the outgoing prompt
  array gives two unarbitrated prompt channels. Sonder's hooks never mutate engine
  structures.
- **One shared settings blob**, where any extension's debounced save writes
  everyone's settings. Sonder: four namespaced homes.
- **Silent failure culture** — load errors console-only for years, swallowed
  handler exceptions. Sonder: per-item load errors with reasons in the UI,
  `disabled_reasons()`, counted observer failures, three-strikes auto-retire.
- **Stack-trace sniffing for attribution.** Sonder forces `ext:<id>` namespacing
  and wraps each extension's bundle in `_begin`/`_end`, so attribution is
  structural and unforgeable.

**Taken deliberately:** zip/URL install as the phase-1 publishing story — their
ecosystem exists because publishing is pushing a repo, and that is worth copying
even though phase 2 diverges from where it left them. Also the manifest as plain
JSON, namespaced routes, and the three-home state instinct (settings / chat /
character), upgraded with checkpoint and branch guarantees they cannot offer.

---

## 7. What building it proved, disproved, or forced

The prototype was built to pressure-test the plan. It changed the plan in
fourteen places; these are the ones that carry a reason.

1. **Discovery caching must be invalidate-only, not eager-rescan.** The
   language-pack template rescans at reset, which caches the directory as it
   looked at reset time. Extension discovery invalidates and rescans on the next
   *read*. Found by eight failing tests.
2. **Splices must be applied grouped-per-anchor in one pass.** Inserting sorted
   splices sequentially against the mutating plan list reverses their order at a
   shared anchor — each insert lands at anchor+1. Pinned by
   `test_two_extensions_at_one_anchor_order_by_id`.
3. **`character:` and `ext:` anchors had to be refused** — not in the plan; see §4.
4. **`on_error="warn"` needs `None → {}` coercion.** `_assert_plan_materialized`
   treats a `None` step value as missing and fails the *turn*, so a "contained"
   handler failure was killing beats anyway. The wrapper coerces `None` and
   non-dict returns.
5. **`char_state` writes are gated like world state, not ungated like settings.**
   `chat_chars.state` is committed per-turn state, so the ghost-state gate
   applies. `request_bind` is the deliberate exception.
6. **`char_state` must honour the frame override.** Commit writes through
   `set_char_state(..., frame_id=...)`, so the facade reads via
   `COALESCE(ccf.state, cc.state)`. A naive base-row write is invisible in a
   framed chat.
7. **`ext:<id>` world keys are chat-global**, not in `FRAME_SCOPED_WORLD_KEYS`,
   so they are shared across eras. A named limitation, not an oversight.
8. **Manifest `stages` are declarations; `add_stage` is the registration.** The
   manifest drives the consent display only. Its `on_error` is informational — the
   `add_stage` argument governs. This split is why §9 of the guide can say
   capabilities are disclosure rather than sandbox.
9. **`#tabs` buttons are bound once at parse time**, before the extension bundle
   (the last script) exists. Extension tabs are therefore rebuilt on every
   `renderSide` with their own handlers. The registries-consulted-per-render
   doctrine survived; the static-binding detail did not.
10. **The UI-catalog scanner constrains host-side extension code.** Every string
    literal in `static/js/*.js` is harvested as translatable, so host strings must
    be genuine reader-facing messages or written as non-literals — the
    three-strikes toast now exists in Japanese. `extensions/**/ui/*.js` is *not*
    scanned; panel strings are the extension's own i18n concern.
11. **A pinned-literal test byte-anchors a line the step-renderer edit wanted to
    change** (`test_pipeline_perspectives.py`), so the edit inserted after the
    anchor instead. Consult-point edits are in tension with literal-pinning tests.
12. **Step persistence for `ext:` keys needed no new machinery.** `save_step` on an
    `ext:` key inherits one-active-variant and reroll.
13. **`agents/README.md`'s add-a-stage checklist now understates** — with the
    splice registry, plan placement no longer requires editing `build_plan`.
14. **Hot enable/disable is live on the server and was reload-only on the
    client.** Found in play, not in tests: enabling an extension made its pipeline
    stage appear on the next turn while its sidebar tab did not.
    `/api/extensions/ui.js` is a `<script>` tag, and a script tag loads once — a
    page loaded while the extension was disabled holds a zero-byte bundle forever.
    Every registry *is* consulted per use, exactly as designed; the bundle's
    ARRIVAL is what was page-bound. Closed in the second batch by serving each
    extension's script and stylesheet separately and injecting them on enable
    (`Sonder._load` / `_unload`). What remains true, and is now stated in the
    guide, is that teardown reaches registrations and injected elements only — a
    monkeypatched global or a `document`-level listener survives a disable, which
    is the honest cost of having no sandbox.

---

## 7a. The second batch, and the one thing it revealed

Six surfaces closed after the first release: `ui.css` served, client-side
hot-load, extension-owned routes under `/x/`, `add_commit_domain` inside the
turn's transaction, `on_character_payload` with attribution, `llm_json`, and a
Director-specialist registry. Only the last two changed the argument.

**`on_character_payload` is where the §1 ruling stops being theory.** Every other
seam narrows by accident-prevention; this one is deliberately unrestricted, and
it is the first place an extension can hand a mind a fact it had no channel to.
What the engine gives in exchange is not restraint but a NAME: the dispatcher
diffs the payload before and after each hook and records which top-level keys
changed, against the extension's id, on the durable turn. The reasoning is
`CLAUDE.md`'s investigation doctrine applied to third-party code — a defect
surfaces where it is rendered and almost never where it originated, and the
single most expensive version of that is a character who knows too much, because
every stage looks innocent. Attribution turns a day of reading stages into one
read of `extensions.routing`.

Top-level keys only, deliberately: a deep diff costs a full walk of the largest
object in the turn on every beat, and the question being answered — *who touched
this mind* — is answered at that resolution.

**The Director specialist registry was the last place "full pipeline access" was
still false.** A specialist lives in six registries (`SPECIALISTS`,
`_CHANNEL_GATES`, `_CHANNEL_SPECIALISTS`, `schemas.SPECIALIST_CHANNELS` plus a
model plus `SCHEMA_MAP`, `prompts.SPECIALIST_PROMPT_SPECS`, `providers.ROLES`),
and they are not independent: `_dispatch_specialists` reads `SPECIALISTS` live
and then indexes `_CHANNEL_GATES` by channel, so patching five of six is not a
degraded specialist but a `KeyError` inside the Director on every beat. Exactly
the shape `add_stage` was built to end, one layer down.

Building it turned up a latent defect in the engine's own code:
`_CHANNEL_SPECIALISTS` was a module-level comprehension over `SPECIALISTS`,
frozen at import. Any family registered afterwards was visible to dispatch and
invisible to `_route_repair_omissions` — a split that routes a repair to nobody
and reports nothing. It is now rebuilt on registration.

Three limits were kept rather than papered over, and each is in the guide:
channels are namespaced `ext:<id>:<channel>` so a family cannot silently take
`attire`; the channels are evidence rather than causality, because no engine
commit domain reads an `ext:` channel; and **nothing narrates them**, because the
prose author's sheet is assembled from in-tree chunks and the one-owner test that
guards it cannot reach across the boundary. That last one is the real residual —
a change recorded in the ledger and absent from the prose is precisely the kind
of defect that takes fifty beats to notice.

---

## 7b. The fourth batch: what a campaign layer needs that a mod does not

Written after Directive's author built against 9.2 and produced a gap report
(`DIRECTIVE_GAP_REPORT.md`; the measurement and the two premises it got wrong
are in [`DIRECTIVE_HOST_SURFACE.md`](DIRECTIVE_HOST_SURFACE.md) §9). Four
surfaces landed. The interesting thing is what the four have in common, which
is not "more access".

**Every earlier seam let an extension participate in a turn. These let it own a
STORY.** A mod runs inside somebody else's game. A campaign layer supplies the
game: it starts the story, holds rules that outlive any beat, has to see the
world between beats to decide anything, and has to show a person only what that
person has. Those are four different verbs, and the batch is one surface each.

**Ordering the routing seams by consequence was the design decision.** There are
now three, and they are not variations on a theme:

| Seam | Changes | If it carries too much |
|---|---|---|
| `on_character_payload` | what one mind believes | a mind acts wrongly, in fiction, recoverably |
| `on_narration_payload` | what the reader is told | already said; cannot be taken back |
| `on_director_payload` | what the engine believes happened | propagates into state, perception and memory, for the rest of the story |

Each row is strictly worse than the one above it, and the Director row is worse
in kind rather than degree: the other two are wrong *about* the world, and this
one is wrong *in* it. That is the argument for the phase split
(`establish`/`interpret`/`resolve`) being mandatory rather than a convenience —
interpret reads what the player declared and resolve decides what it achieved,
and an author who cannot tell those apart writes an interpretive constraint that
silently vetoes outcomes. It is also why the block arrives ATTRIBUTED and
alongside every other extension's, rather than named in the prompt as
authority: the report's own safeguard list asked that an extension not be able
to impersonate an engine-owned instruction, and the way to honour that is to
give it the same standing as every other contributor rather than to trust it
less.

**The projection is the first surface where the §1 ruling has an exception, and
the exception proves it.** §1 says the firewall is for minds, not developers,
and `story_view` is flatly canonical on that basis. `player_view` is not — but
not because an extension is untrusted. It is because the extension asked for
"what does this person have", and that question has exactly one correct answer
in this engine, held by `agents/perception.py`. The temptation was to compute it
here from the objective scene. That would be a second implementation, agreeing
with the first on the day it was written and drifting silently forever after —
and silently is precise: a projection is never narrated, so no reader would ever
encounter the leak. So the projection **returns what was already delivered**:
the perception stage's own view and observations, the viewer's own memories and
relationships, the identity ledger's own answer about who they can name. It
decides nothing. It is a different kind of guard from the rest of this engine's
— not a subtraction, but a refusal to compute.

Its second property is `absent means absent`. A field it cannot answer is
missing rather than `null`, defaulted, or deduced. A UI renders a guess and a
fact identically, and the report was right to make this an absolute rather than
a preference.

**Provisioning was answered by refusing to build it.** The report asked for a
declarative campaign package. It got the chat archive, because the list a
campaign needs to be coherent from turn one — story, persona, cast with stable
ids, rooms, portals, positions, scene, clock, lore on both sides of the
firewall, relationships — is the same list a branch and a restore already have
to get right, atomically. A second importer is a second copy of those bugs. What
was genuinely missing was one thing an archive cannot do: seed the extension's
own namespaced state inside the SAME transaction, so a story cannot exist with
no campaign attached and still look playable in the list.

**And the fifth gap was not an extension surface at all.** Hard mode
(`PlayerAuthorityMode`) had sat in `UNBUILT.md` §2.4 as this engine's own
long-standing debt, and an outside integrator hit it from the other direction
and asked for it as a host requirement. That is worth recording as a fact about
extension work: the surfaces a third party needs are a reasonable proxy for the
features the engine was already missing, because a third party has no way to
route around them.

## 8. What is left

In [`UNBUILT.md`](../UNBUILT.md) §6.2, which is the status list. In short:
declarative advisor stages; the two admission-side routing hooks (`on_admission`,
`on_view`); a prose-author chunk registry so an extension specialist's channel can
be narrated (§7a); the `--extension` self-check CLI; the scoped-client work that
would make third-party frontends real for non-host players; and phase 2's
registry. From the fourth batch (§7b): a notification surface, a settings-section
mount point, extension-declared model lanes, document storage, and the browser
chat lifecycle as a declared contract — none of which blocked a first campaign
integration, on the integrator's own assessment.

What is not a surface and is the next real piece of work: a REFERENCE CAMPAIGN.
One room change, two characters, one secret, one gated objective and one
forbidden invented player line exercises all four new contracts plus hard mode
end to end, and nothing in this tree currently does.
