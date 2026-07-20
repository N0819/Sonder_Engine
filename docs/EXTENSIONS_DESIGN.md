# Extension System — Design Notes (exploratory, not yet built)

Status: **design exploration for a future feature.** Nothing here is implemented.
Captures how user-authored extensions (UI changes + pipeline interaction) could be
added to Sonder Engine, grounded in the existing seams. Verify file:line anchors
against current code before acting — they drift.

---

## 0. What the codebase already gives you

Three de-facto extension mechanisms already exist and should be the skeleton, not
replaced:

1. **`agents/runtime.py:register_step()`** (~line 170) — an explicit, tested
   (`tests/test_agent_package.py`) API for registering a pipeline step handler
   without editing dispatch, with a reserved `character:<id>` namespace guard. Its
   docstring deliberately punts on the missing half: *plan placement* — there is no
   hook to splice a registered step into `build_plan()` (runtime.py ~365) or
   `establishment_plan()` (~461). **That splice hook is the single biggest missing
   piece of a pipeline extension story.**
2. **Prompt presets** — `prompts.py:get_prompt()` resolves `active_preset` →
   `prompt_presets` (settings-stored JSON) → `DEFAULT_PROMPTS`, with CRUD at
   `PUT /api/prompt_presets` / `PUT /api/active_preset`. A prompt-override extension
   is already just data.
3. **Data-driven providers and role models** — providers live in a DB table
   (`providers.py:provider()`, `POST /api/providers`); per-role model choice is the
   `agent_models` setting (`resolve_role_candidates()` with fallbacks). Per-chat
   behavioral config is world-KV: `scene.py:dialogue_config()/reaction_config()/
   background_config()/fiction_model()`, all read via `wget`.

Also: any unknown key assigned into `PipelineContext` lands in `_extra`
(`pipeline_context.py`), and any step run via `_step_stream` → `storage.save_step`
automatically gets `steps`/`variants` rows — so an extension stage inherits reroll,
one-active-variant, staleness, and the pipeline drawer **for free**, provided it
appears in the plan deterministically.

---

## 1. Extension surfaces and taxonomy

### (a) Pipeline surfaces

| Want | Real seam | Status |
|---|---|---|
| Inject a custom stage | `runtime.register_step()` + a new **plan-splice registry** consulted inside `build_plan()`/`establishment_plan()` at named anchors (`after:perception_outcome`, `before:narrator`, …) | Handler half exists; splice half must be added (small, contained) |
| Pre/post hook on an existing stage | Wrap in `runtime.compute_step()` — the one chokepoint every step passes through | Feasible; dangerous (see §4) |
| Transform a stage's output | Same chokepoint, post-handler | Same danger; defer |
| New deterministic commit domain | `commit.py:_commit_all_locked()` — a registry of extra `_commit_domain(...)` calls in the same `transaction()`; plus a post-commit observer slot next to `_consolidate_committed_memories` | Clean fit with existing `_commit_domain` structure |
| New provider | Already data: `POST /api/providers` | Exists |
| Prompt overrides | `prompts.py:presets()` / `get_prompt()` | Exists |
| Per-chat behavior presets | `wset` keys read by `scene.py:dialogue_config()` etc. | Exists (needs a bundling format) |

### (b) UI surfaces (browser globals, no ES modules — every hook is a registry core render fns consult)

| Want | Real seam |
|---|---|
| Header button | `#top` in `static/index.html`; existing buttons via `$("#b-world").onclick` in `settings.js` |
| Sidebar tab + list | `renderSide()` in `app.js` (`S.tab` switch) |
| Settings pane | tab arrays inside the `#b-cast` modal builder (`settings.js`) |
| Custom turn action / decoration | `renderChat()` in `chat.js` — the `.turn` div and `.tbtns` row |
| Narration render decorator | Same prose node; `detectSceneMood()/applySceneMood()` (chat.js) is an in-tree example |
| Pipeline-step visualization | `openPipeline()` (chat.js) — per-step-key renderer registry |
| Live stream tap | `handleEvt()` (chat.js) — every `step_start`/`token`/`step` event flows through here |
| Modal/panel primitives | `el()` and `modal()`/`closeModal()` in `components.js` |

---

## 2. The "easily written" spectrum

- **Tier 0 — pure data bundle ("story pack").** JSON manifest bundling prompt-preset
  overrides, per-chat config defaults (applied by `newChatWizard`, app.js), lorebooks,
  characters. Zero code, zero risk beyond prompt injection. ~80% of what hobbyist
  authors want.
- **Tier 1 — declarative manifest with two generative primitives (recommended first ship).**
  - *Declarative UI*: buttons/panels as data (`{placement, label, action:{endpoint, render}}`);
    author writes no JS.
  - *Declarative "advisor stage"*: a stage as data — role, prompt, an **input-scope
    whitelist**, an anchor slot. Engine assembles payload from whitelisted scopes, so
    the epistemic firewall is enforced **by construction**.
- **Tier 2 — structured Python/JS plugins.** `extensions/<name>/hooks.py` exposing
  `register(api)` with a narrow capability API; a JS file registering panels via
  `window.Sonder.*`. Real power, *advisory* safety only (in-process Python can `import db`).
- **Tier 3 — arbitrary plugins.** Tier 2 with no pretense of constraint.

**Sweet spot: ship Tier 0+1 together.** The advisor stage is the novel, high-leverage
piece — a "foreshadowing critic", "combat referee note", "weather sim" stage that shows
up in the pipeline drawer with reroll/variants working, no code, and *cannot* breach the
firewall. Skip the sandboxed-DSL tier (near-tier-2 cost, near-tier-1 power).

---

## 3. Concrete minimal design (Tier 1)

**Discovery/loading.** `extensions/<name>/manifest.json` scanned at startup from
`_startup_engine()` (app.py) and via new host-only endpoints (`GET/POST /api/extensions`,
enable/disable persisted as an `enabled_extensions` settings key). Manifest:

```json
{
  "id": "foreshadow-critic", "version": "1",
  "capabilities": ["prompts", "ui:button", "stage:read:narration,director_resolve"],
  "prompts": { "narrator": "…preset text…" },
  "chat_defaults": { "background_config": { "max_reactors": 2 } },
  "ui": [ { "placement": "turn-button", "label": "Critique",
            "action": { "endpoint": "/api/turns/{tid}/pipeline", "render": "step:foreshadow" } } ],
  "stages": [ { "key": "ext:foreshadow-critic", "label": "Critic · foreshadowing",
                "anchor": "after:narrator", "role": "default",
                "reads": ["narrator", "director_resolve", "recent_events"],
                "prompt": "…", "on_error": "warn" } ]
}
```

**Namespacing:** extension step keys forced into `ext:<id>` — mirror the existing
`character:` reservation in `register_step()`.

**Plan integration (the one core change).** `build_plan()`/`establishment_plan()` end
with `plan = _apply_extension_splices(plan, chat_id)`, splices from the enabled set,
ordered by anchor then id. Must be a **pure function of (enabled set, interp, chat
config)** because `resume_key_for_turn()` and the `from_key` paths recompute the plan
from stored `director_interpret` content — nondeterminism breaks resume. Enable/disable
mid-history is the same plan-change class the runtime already survives (orphan-step logic
deletes single-variant orphans, preserves rerolled ones).

**Stage execution scopes.** Generic handler assembles the payload only from an
engine-controlled whitelist:
- Safe: `narrator`, `director_interpret`, `director_resolve`, `perception_outcome`
  *player* view, `recent_events`, `simulation_clock`, `fiction_model`.
- Never in Tier 1: other characters' `perception_act`/`interaction_views`,
  `ctx.character_results`, `private_knowledge_for`, memory internals.

Crucially, **no built-in stage reads `ext:*` output** — a declarative stage is an
*annotator*: its output is a step (visible in `openPipeline`, renderable by the UI entry,
available to the next turn's player) but cannot flow into a character payload. Influence
on characters goes through legitimate surfaces (prompt presets, `dialogue_config`).

**Failure containment.** `on_error: "warn"` catches exceptions, materializes
`{"error": …}` as step content, appends to `ctx.warnings` — satisfying
`_assert_plan_materialized` and one-active-variant without a flaky stage killing turns.
`on_error: "fail"` opts into normal step failure.

**Persistence.** Tier 1 stages persist nothing outside `steps`/`variants` — sidesteps the
whole DATABASE.md checklist because step rows already ride branch/export/checkpoint
machinery. A Tier 2 `register_commit_domain(name, fn)` runs inside
`_commit_all_locked`'s transaction (after `narration_person`, before `pending`),
inheriting atomic rollback — with the obligation that any new table must join
checkpoint/export coverage or reruns silently diverge.

**UI loading.** One new script tag in `static/index.html` **after** `app.js`:
`<script src="/api/extensions/ui.js">` — served as the concatenation of enabled
extensions' declarative-UI bootstrap (and, at Tier 2, raw JS). Loading last means every
global (`$`, `el`, `modal`, `api`, `S`, `boot`) exists. Serving under `/api/` (not
`/static/`) matters: `access_control` only guards `/api/*`, keeping extension code
session-gated — and because guests get the separate `guest.html` with a two-endpoint
allowlist, **extension JS never reaches guests**.

`window.Sonder` registry: `registerHeaderButton`, `registerTab`, `registerTurnAction`,
`registerTurnDecorator`, `registerStepRenderer(key, fn)`, `onStreamEvent(fn)`,
`refresh()`. Core render fns consult registries every call (`renderSide`, `renderChat`,
`openPipeline`, `handleEvt`) — so late registration is a non-issue; `Sonder.refresh()`
forces a render.

---

## 4. Safety and the hard problems

**Threat model, three tiers:**
1. *Local single-user, self-authored*: author owns the machine + `engine.db`. "Safety" =
   protecting invariants from *accident*, not malice.
2. *Shared guest links*: already contained (guests hit `guest.html` + two-path allowlist,
   never load SPA scripts). Keep it: never inject extension JS into the guest page; never
   let a manifest widen `GUEST_ALLOWED_API_PATHS`.
3. *Community-distributed extensions*: the real danger. A Tier 2/3 Python extension is
   arbitrary code execution (read `engine.db`, exfiltrate, persist malware). A Tier 2/3 JS
   extension runs same-realm with the host cookie and can call **every** host API —
   including `GET /api/bootstrap`, which exposes provider API keys. A malicious "theme"
   that steals keys is a one-liner.

**Firewall breaks by accident.** A naive "pre-stage hook gets full ctx" makes it one line:
copy `ctx["director_resolve"]["outcome"]` or another character's `interaction_views` into
a character payload's `perception.view` (assembled at `agents/character.py`) → invariant
violated. So Tier 1 forbids payload mutation entirely; Tier 2's `api` facade exposes
*scoped getters*, never `ctx`. If payload-transform hooks are ever added, the hook must run
*inside* `character_step` after payload assembly (redact/append only), never the surrounding
ctx.

**Persistence boundary breaks.** A hook calling `qi()`/`wset()` mid-pipeline writes outside
the commit transaction: a later domain failure rolls back everything *except* that write,
and `restore_checkpoint` won't cover extension tables absent snapshot integration → ghost
state on rerun. Enforcement is impossible in-process; mitigation = API shape (no DB handle;
give `register_commit_domain` + `on_turn_committed`) + a `tools/project_check.py`-style lint
flagging `import db` in `extensions/`.

**Sandboxing, honestly.** In-process Python sandboxing (RestrictedPython, builtins-strip) is
not a security boundary — don't claim it. Real options: (a) subprocess extension host over
JSON/stdio with timeouts — genuine isolation, meaningful build cost, reasonable eventual home
for untrusted stage logic; (b) WASM — overkill. JS: `<iframe sandbox>` + postMessage gives
real containment but kills the pleasant `el()`/`modal()` integration; a CSP with same-origin
`connect-src` blocks only naive exfiltration. **Achievable posture: Tier 0/1 are actually
safe (data-only, engine-interpreted, capabilities enforced); Tier 2/3 are trusted code behind
an explicit consent screen** ("This extension can run code with full access to your database
and API keys") — the Obsidian/VS Code model, stated plainly.

---

## 5. Roadmap

1. **Rung 1 (days):** Story packs — manifest import/export bundling prompt presets +
   chat-default configs + lorebooks; a "Packs" section in settings. Pure data over existing
   endpoints; no new invariant exposure.
2. **Rung 2 (the real ship):** Tier 1 — extension loader + settings key, plan-splice hook in
   `build_plan`/`establishment_plan`, generic declarative-stage handler over `register_step`,
   `ext:` key reservation, `/api/extensions/ui.js` + `window.Sonder` registries, per-step
   renderer in `openPipeline`. Regression tests: resume/reroll with an extension stage
   enabled; disable-mid-history orphan behavior; a test asserting the scope whitelist never
   exposes `character_results`/private views.
3. **Rung 3:** Tier 2 Python `register(api)` with scoped getters, `register_commit_domain`
   (inside the transaction) and `on_turn_committed` (post-commit, warn-only), plus the consent
   screen and the `import db` lint.
4. **Rung 4 (only if community distribution materializes):** subprocess extension host for
   untrusted stage logic; signed/curated pack index.

**Invariant conflicts to keep off the roadmap until designed:** payload-mutating hooks
(conflict with information-boundary invariants — off until the inside-`character_step` design
exists); extension-owned tables (conflict with the persistence checklist unless
checkpoint/export integration ships in the same rung); anything varying the plan
non-deterministically (breaks `resume_key_for_turn` — plan splices must derive only from
durable settings).
