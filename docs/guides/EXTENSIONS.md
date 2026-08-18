# Extensions — developer guide

Authority for the extension system as built. If this file and
[`docs/design/EXTENSIONS_DESIGN.md`](../design/EXTENSIONS_DESIGN.md) disagree,
this one is right — the design note argues *why*, this one states *what*.
Unfinished pieces are registered in [`docs/UNBUILT.md`](../UNBUILT.md) §6.2.

An extension is a directory, installed from a git repository, a zip, or a
folder. It can add pipeline stages, observe every step,
persist per-story and per-character state, read a character's interior, add
sidebar tabs, toolbar buttons, composer controls, full-window views and step
renderers, colour what the narrator is told, serve its own HTTP routes' worth of
data, and restyle or replace the entire interface. It does all of that without editing a
single engine file.

---

## 1. What an extension is

```
extensions/
  my-extension/
    manifest.json      # required
    extension.py       # optional — the Python half
    ui/
      panel.js         # optional — the browser half
```

The root is `extensions/` beside `app.py`. Override it with the `SONDER_EXTENSIONS`
environment variable — read at **call** time, so a test or a second library only
has to set it.

`SONDER_EXTENSIONS_SAFE=1` boots with nothing enabled and no extension code
imported at all. That is the escape hatch for an extension that breaks the app
badly enough that you cannot reach the menu to disable it.

Discovery is **per-item**: a malformed extension lands in `load_errors()` with a
reason and every sibling loads normally. Nothing an extension does can make
`import app` fail — discovery is lazy, and every dispatch helper the engine calls
is total (on internal failure it logs and returns the safe value).

---

## 2. The manifest

```json
{
  "id": "cohesion-demo",
  "version": "0.1.0",
  "ext_api": 1,
  "name": "Cohesion (demo)",
  "description": "One deterministic stage after the Director resolves, and a per-story score.",
  "capabilities": {
    "stages": [
      {"key": "pulse", "anchor": "after:director_resolve", "label": "Cohesion · pulse"}
    ],
    "chat_state": true,
    "characters": ["observe"],
    "python": "extension.py",
    "ui": {"js": "ui/panel.js"}
  }
}
```

| Field | Rule |
|---|---|
| `id` | `^[a-z][a-z0-9_-]{1,63}$`, and **must equal the directory name** |
| `version` | dotted digits (`1`, `0.1.0`, `2.14.3`) |
| `ext_api` | must be exactly `1` — a mismatch is a load error, not a warning |
| `name`, `description` | free text, shown in the Extensions menu |
| `capabilities` | an object; see below |

Unknown manifest keys are **tolerated on purpose** so a manifest written for a
later `ext_api` stays readable rather than becoming an error.

### Capabilities

`capabilities` is a **disclosure**, not a sandbox. Every entry is parsed,
displayed to the host on the consent dialog, and used to compute the trust
class — but **nothing enforces it at runtime**. An extension that declares
`"characters": ["observe"]` and then writes character state is not stopped. This
is deliberate: the security model is host consent plus (later) a review
registry, not a capability sandbox. See §9.

| Key | Meaning | Enforced? |
|---|---|---|
| `stages` | list of `{key, anchor, label}` — declares stages you will register | Validated for shape only |
| `chat_state` | you keep per-story state | No |
| `char_state` | you keep per-character state | No |
| `characters` | e.g. `["observe"]`, `["observe", "write"]` | No |
| `routing` | you alter information routing | No |
| `system` | full pipeline access | No |
| `python` | relative path to your Python entry | Yes — containment-checked |
| `routes` | HTTP routes you serve | No |
| `commit_domains` | you write inside the turn transaction | No |
| `ui` | `{"js": "...", "module": "...", "css": "..."}` | All served |

`ui.js` and `ui.module` are two ways in, not a choice you have to make once.
`js` is a **classic script**, concatenated with every other extension's into one
bundle — right for a panel, and unable to contain `import`. `module` is an **ES
module entry**, fetched on its own so its own imports resolve, which is what any
extension built as more than one file needs. Declare both while you move files
across; both are served. Section 7.5 has the loading contract.

Each `stages` entry must have a non-empty `key` and `anchor` or the manifest
fails to load. That validation is all the manifest does for stages — the actual
registration happens in Python (§4).

### Trust classes

Computed, not declared — `data` < `prompt` < `code`:

- **`code`** — declares `python`, `ui.js` or `ui.module`, **or** has any
  `.py`/`.js`/`.mjs` file anywhere in its tree. Declared-or-present, because a
  script sitting in the directory is code the moment the host enables it,
  whether the manifest admits to it or not.
- **`prompt`** — ships prompt text (`prompts`, `prompt_presets`, or a stage with
  a `prompt`).
- **`data`** — everything else.

The class drives the wording of the consent dialog. A `code` extension is told
plainly that it runs with the engine's own access.

---

## 3. Lifecycle

**Install** — `POST /api/extensions/install` with `{"source": "..."}`, or the
field at the bottom of the 🧩 Extensions menu. A source is one of three things,
and which one is decided before anything is fetched:

| Source | Recognised by |
|---|---|
| **a git repository** | ending in `.git`, a `git+` prefix, a `file://` URL, or an ordinary `https://github.com/owner/repo` on a known forge (GitHub, GitLab, Codeberg, Bitbucket, sourcehut) |
| **a zip** | any other `http(s)` URL |
| **a folder** | anything else |

Append `#branch` or `#tag` to a repository URL to follow that instead of the
default branch: `https://github.com/owner/repo#v2`.

Only `http(s)` and `file://` can be cloned. `ssh://`, `git@host:path`, `git://`
and `ext::` are refused — and the ssh case matters most, because it would not
fail, it would **hang**: without a key, git blocks on a passphrase prompt inside
a web request with nobody at the terminal to answer it. Submodules are never
initialised; a submodule is a second URL chosen by the repository rather than
by the host, and it can name any transport.

A clone keeps the working tree and discards `.git`. Updates re-clone, so there
is no repository state on your disk to drift, conflict with a local edit, or
fail halfway.

The install is staged, validated and then moved with `os.replace`, so an install
interrupted at any point leaves either the old extension or none — never a
half-written directory that fails to load forever. Specifically:

- Archives are capped at **32 MB**.
- **Zip-slip and symlinks are refused** before extraction: any member naming an
  absolute path, a `..` component, or carrying the symlink bit aborts the whole
  install.
- A bundle wrapped one level deep (`zip -r ext.zip my-extension/`) is unwrapped,
  because that is what people actually produce.
- The staged directory is renamed to its **declared id** before validation, so
  the archive's own directory name does not matter.
- `provenance` (`url:…` or `local:…`) and, for URL installs, `sha256` are
  written into the installed manifest — so a future reviewed-registry phase can
  tell a reviewed install from a sideloaded one without re-deriving it.
- A repository is audited on the same ceilings as an archive — no symlinks, no
  more than 4096 files, no more than 256 MB expanded — because a repository can
  hold all three just as happily as a zip can.
- Installing over an existing id is **refused**. Remove first.

**Enable / disable** — `POST /api/extensions/{id}/enable` / `…/disable`. The
enabled set is a JSON list in the `enabled_extensions` setting. Enabling imports
your Python entry and calls `register(api)` exactly once.

**Update** — `GET /api/extensions/updates` asks every git-sourced extension's
remote whether it has moved (one `ls-remote` each, no download), and
`POST /api/extensions/{id}/update` takes the newer commit. In the menu these
are the **Check for updates** button and a per-extension **Update** button that
appears only once a check has said there is one.

Three properties worth knowing:

- **Only a repository install can be checked.** A zip would have to be
  downloaded in full to compare, and a folder has no upstream — both report
  `checkable: false` with the reason rather than claiming to be up to date,
  which is the same claim with the truth removed.
- **A check never raises.** An unreachable remote is reported on its own row, so
  one dead repository cannot fail the sweep for everything else.
- **A bad upstream commit cannot take your working copy down.** The new tree is
  cloned and validated in staging before the installed one is touched, and if
  the swap fails the old directory goes back. A repository that renames its own
  `id` is refused rather than updated into, since that would hand one
  extension's stored story state to another.

The enabled set and everything under `world["ext:<id>"]` survive an update: it
is the same extension, so a story played with it keeps going.

**Remove** — `DELETE /api/extensions/{id}`. Deletes the directory and **leaves
`world["ext:<id>"]` alone**: removal takes the code, not the history, so
reinstalling picks a story back up rather than starting it over.

### Hot-loading, honestly

Enable and disable are **live on the server**: `activate()` is called from every
seam, so a stage joins the very next turn's plan and a disabled extension's
handlers are gone immediately.

They are live in the browser too, with one caveat worth knowing. The page-load
path is a single `<script>` tag and a script tag loads once, so the host cannot
rely on it after boot; instead the Extensions menu calls `Sonder._load(id)`,
which fetches `/api/extensions/<id>/ui.js` and `…/ui.css` and appends them to
the live page, and `Sonder._unload(id)` on disable, which drops every
registration you made and removes both elements.

**The caveat:** `_unload` can only undo what went through the registry. A global
you monkeypatched, a timer you started, a listener you added straight to
`document` — those survive. If your extension does any of that and you want it
cleanly disableable, undo it yourself in a `turn:*` handler or expose your own
teardown. Otherwise a disable is honest about your panel and quiet about your
side effects.

If you drive the routes yourself rather than through the menu, reload the page
after toggling.

---

## 4. The Python half

`capabilities.python` names a file inside your directory. The loader resolves it,
checks containment, imports it under a name **it** constructs (`sonder_ext_<id>`),
and calls `register(api)`. A manifest never names a module path, so no JSON string
can make the engine import something outside your directory.

```python
def register(api):
    """Called ONCE when the host enables this extension."""
```

If `register` raises, your extension is disabled with the exception message
readable in the Extensions menu, and **every sibling stays live**.

### `api` — the whole surface

| Member | What it is |
|---|---|
| `api.id` | your extension id |
| `api.data_path` | `Path` to your own directory |
| `api.log` | a logger named `ext.<id>` |
| `api.characters` | character access (§5) |
| `api.add_stage(key, *, anchor, label=None, handler=None, on_error="warn")` | register a stage **and its position** |
| `api.on_step(pattern, fn)` | observe every saved step matching an fnmatch pattern |
| `api.on_turn_committed(fn)` | run after a turn is durable, outside the transaction |
| `api.add_commit_domain(name, fn, on_error=...)` | run **inside** the turn's transaction |
| `api.on_character_payload(fn)` | rewrite what one mind is about to be given |
| `api.on_narration_payload(fn)` | rewrite what the narrator is about to be given |
| `api.on_director_payload(fn)` | rewrite what the Director is about to be given |
| `api.narration_context(chat_id)` | standing context for the narrator |
| `api.director_context(chat_id)` | standing campaign rules for the Director |
| `api.story_view(chat_id)` | canonical story state, versioned and read-only |
| `api.player_view(chat_id, viewer)` | what one person in the story may be shown |
| `api.viewers(chat_id)` | the viewer ids `player_view` accepts |
| `api.provision_story(package, state=..., ...)` | create a whole story atomically |
| `api.provenance(chat_id)` | what you recorded when you provisioned it |
| `api.add_director_specialist(name, channels=..., prompt=...)` | a seventh Director family |
| `api.add_route(path, fn, methods=...)` | serve your own HTTP route |
| `api.llm_json(system, payload, role=...)` / `api.llm_text(...)` | a model call on a configured role |
| `api.state(chat_id)` | per-story state |
| `api.settings` | install-scoped config |
| `api.char_state(chat_id, char_id)` | per-character state |

You do **not** get a `PipelineContext`, a database handle, or another character's
private view. See §8 for why, and for what to do if you want them anyway.

### Adding a stage

```python
def pulse(view, api, nonce):
    return {"cohesion_delta": 1, "evidence": ["..."]}

def register(api):
    key = api.add_stage(
        "pulse",
        anchor="after:director_resolve",
        label="Cohesion · pulse",
        handler=pulse,
        on_error="warn",
    )   # -> "ext:cohesion-demo:pulse"
```

- `key` matches `^[a-z][a-z0-9_-]{0,63}$`; the real step key becomes
  `ext:<your-id>:<key>`, so two extensions can both call a stage `pulse`.
- `anchor` is `after:<step>` or `before:<step>` naming a **core** step
  (`director_interpret`, `mapping_stage`, `perception_act`, `interaction_loop`,
  `director_resolve`, `background_react`, `perception_outcome`, `narrator`,
  `commit`, …). See [`PIPELINE.md`](PIPELINE.md) for the full plan.
- Anchoring on `character:*` or `ext:*` is **ignored**. The character group is
  planned as a parallel fan-out and splicing into the middle of it would silently
  serialize it.
- An anchor naming a step **this particular turn does not run** means your stage
  is simply not planned that turn. Not an error, and — importantly — not bolted
  onto a different position, which would make the plan differ between the live
  run and the recompute.
- `on_error="warn"` (default) turns an exception into `{"error": "..."}` as the
  step's content plus a turn warning. `on_error="fail"` opts into normal step
  failure, which kills the turn.

**Your handler must return a dict.** `None` becomes `{}`, a non-dict becomes
`{"value": ...}`. This matters because `_assert_plan_materialized` requires
exactly one active variant per planned key — a stage that persists nothing fails
the whole turn's materialization check, far from the interesting failure.

Because your stage is a normal `steps`/`variants` row, it inherits **reroll,
one-active-variant, staleness, branch, checkpoint, archive and the pipeline
drawer for free**. You do not add a row to `schemas.SCHEMA_MAP`, a field to
`PipelineContext`, or a line to `commit.py`. The
[add-a-stage checklist](../../agents/README.md) is for *engine* stages; none of it
applies to you.

**The plan splice must stay a pure function of durable settings plus manifests.**
`resume_key_for_turn` and every `from_key` path rebuild the plan from stored step
content, so a splice that varied with the clock, a random draw, or live model
output would break resume. Do not make `register` conditional on anything that
is not persisted.

### `view` — what a stage receives

`StepView` is a read-only slice of the running turn. Finished step output only —
nothing still being assembled.

| Member | Value |
|---|---|
| `view.chat_id`, `view.turn_idx`, `view.turn_id`, `view.frame_id` | identity |
| `view.step(key)` | any completed step's content this turn, or `None` |
| `view.resolve` | `director_resolve` content, `{}` if absent |
| `view.state_diff` | `resolve["state_diff"]`, `{}` if absent |
| `view.resolved_event` | `resolve["resolved_event"]`, `""` if absent |
| `view.dialogue_log` | `resolve["dialogue_log"]`, `[]` if absent |

`nonce` is the runtime's per-attempt token; pass it through if you make a model
call so reroll behaves.

### Observing steps

```python
api.on_step("character:*", lambda key, content: ...)
api.on_step("*", record_everything)
```

Fired when a step's content becomes durable. Read-only by construction: you get
the key and the content, never the context, so you cannot feed one stage's output
into another's payload through this seam. A throwing observer is counted in
`observer_failures()` and logged; it never fails a turn.

### The committed-turn hook

```python
@api.on_turn_committed
def apply(turn):
    state = dict(turn.state.get({"cohesion": 50}))
    state["cohesion"] += turn.step_content("ext:my-ext:pulse")["cohesion_delta"]
    turn.state.set(state)
```

`turn` is a `CommittedTurn`: `chat_id`, `turn_idx`, `turn_id`,
`step_content(key)` (context first, then storage), and `state` — the per-story
`ExtState`, already bound.

This runs in `commit.py`'s tail, **after** the turn's facts are durable, inside a
commit scope. A hook that raises produces a turn warning and an entry in the
commit result's `extensions.errors`; it never rolls the turn back.

### Writing inside the turn's transaction

`on_turn_committed` runs *after* the transaction closes. When you need a write
that is atomic **with** the turn — rolled back if the beat is — register a commit
domain instead:

```python
def keep(view):
    view.state.set({"beats": (view.state.get({}) or {}).get("beats", 0) + 1})

api.add_commit_domain("tally", keep)             # on_error="warn"
api.add_commit_domain("critical", keep, on_error="fail")
```

`view` is a `CommitView`: `chat_id`, `turn_idx`, `turn_id`, `step_content(key)`,
`state`, and `char_state(char_id)`. State reached from here is **ungated** —
outside a transaction the gate exists to stop a write surviving a rollback, and
inside one that hazard is gone.

Domains run last inside the transaction, after every engine domain, so you can
read what the turn just made durable. They run in `(extension id, name)` order.

`on_error="warn"` keeps the engine's promise that a broken extension never costs
a turn: the failure becomes a warning and the transaction continues.
`on_error="fail"` **rolls the turn back**. It is the one way an extension can
legitimately kill a beat, and it is right only when your state being wrong is
worse than the beat being lost.

### Your own HTTP routes

```python
def history(request):
    return {"history": api.state(request.chat_id).get({}) or {}}

api.add_route("/history", history, methods=("GET",))
# -> /api/extensions/<your-id>/x/history
```

Everything you serve lives under `/x/`, so you can name a route `disable` or
`state` without shadowing a host route. `request` is the engine's own shim —
`.method`, `.path`, `.query`, `.body`, and `.chat_id` for the parameter almost
every route wants. The return value is JSON-encoded. Raise `ExtensionError` for
a 404, anything else for a 500. From the browser: `Sonder.call(id, "GET", "/x/history?chat_id=" + chatId)`.

### Model calls

```python
verdict = api.llm_json("You judge tone.", {"beat": view.resolved_event},
                       role="utility")
prose = api.llm_text("You write epigraphs.", "A door closed.", role="default")
```

Loose on purpose. `_agent_json`, the engine's own path, validates against
`schemas.SCHEMA_MAP`, which only knows the engine's steps — you own your output's
shape, so you get the parse and not the schema. Roles come from the host's
configured `agent_models`.

### Adding a Director specialist

The Director is not one mind: each stage fans out to a prose author plus six
scoped specialists, each owning a subset of `state_diff`'s channels. You can add
a seventh.

```python
api.add_director_specialist(
    "morale",
    channels=["morale_ops"],
    prompt="Judge how the crew's morale moved this beat.",
    gate=lambda facts: facts["physical_beat"] or facts["speech_present"],
)   # -> "ext:<your-id>:morale", owning "ext:<your-id>:morale_ops"
```

It joins the real fan-out: same scope gating, same parallelism, same fail-open (a
failed specialist leaves the stage author's channels standing and never kills a
beat), same canonical merge order. Omit `gate` and it runs on physical beats,
which is the fail-open rule the engine's own gates follow.

Three things it deliberately is **not**:

- **Your channels are namespaced `ext:<id>:<channel>`.** You cannot own `attire`
  or `positions`. A family that could would not error — it would silently take
  the body or spatial specialist's channel in the merge.
- **Your channels are evidence, not causality.** No engine commit domain reads an
  `ext:` channel, so what you write lands in the merged `state_diff` and changes
  nothing by itself. Act on it from your own commit domain or stage.
- **Nothing narrates it.** The prose author's sheet is assembled from in-tree
  chunks and you cannot add one, so a change you record reaches the ledger and
  not the prose unless you put it there. "It committed but nobody mentioned it"
  is otherwise a fifty-beat mystery.

Your specialist also gets only the **shared** payload — the beat, declared
attempts, final dice, the roster. The per-family ledgers (`attire` for body,
contact ledgers for contact) belong to the families that own them.

### Rerouting what a mind receives

```python
@api.on_character_payload
def brief(payload, info):
    if info.name != "Ash":
        return None
    return {**payload, "briefing": "the klaxon sounded"}
```

Runs after `character_step` has assembled a character's payload and immediately
before the model sees it. Return a dict to replace it, `None` to leave it. `info`
carries `char_id`, `name`, `chat_id`, `turn_idx`, and `step(key)`.

Unrestricted — add, remove, rewrite. What the engine guarantees in exchange is
**attribution**: every top-level key you change is recorded against your id and
rides the turn's commit results under `extensions.routing`, so a mind that knows
something it should not names you in one read instead of looking like an engine
defect. A hook that throws leaves the payload exactly as assembled.

Read §8 before using this one. It is the seam where the firewall guarantee stops
describing Sonder's pipeline and starts being yours.

### Colouring what the narrator is told

The other direction. `on_character_payload` decides what a MIND is given;
this decides what the **reader** is given, and there are two ways in.

**Standing context** — a stored block, which is what a layer that says the same
thing every beat actually wants:

```python
api.narration_context(chat_id).set(
    "The ship is three days into a fuel emergency; corridors are dim and cold.")
```

Installed once, it rides every beat of that story inside the narrator's payload
under `extension_context`, attributed to you, until you `.clear()` it. It is one
block per extension per story, **replaced** rather than appended to — a context
injector that appends leaks everything it ever said. Re-setting identical text
does not bump `revision`, so a `sync`-shaped caller that re-installs every beat
does not drive the number to the turn count. It lives in the `world` KV under
`ext:<id>:narration`, so it rides checkpoints, archives, branches and clones
with everything else in that namespace. Writes are **ungated** — a block is
installed by a host action that has no turn transaction to belong to, the same
reasoning as `request_bind`. The ceiling is 8000 characters, refused rather than
truncated, because the cost is paid on every beat rather than once.

**The hook**, when a block is not enough:

```python
@api.on_narration_payload
def frame(payload, info):
    if info.scope != "narrator":
        return None
    return {**payload, "extension_context": [...]}
```

Blocks are assembled first and hooks run second, so a hook can see and replace
what the declarative half just built. `info` carries `scope`, `player`,
`chat_id`, `turn_idx`, `turn_id` and `step(key)`.

**Read `info.scope`.** The narrator runs once for the main reader (`"narrator"`)
and again per extra player (`"narrator_extra"`), each with their own
perception-filtered view. A hook that colours only one of them hands two people
at the same table different stories, and it surfaces as a continuity complaint
from one seat only.

Both run **once per beat**, not once per attempt: the narrator re-enters
generation for a fidelity correction and up to twice more for craft rewrites,
and all of those reuse the hooked payload. A hook re-run per attempt could hand
each attempt different context, and the retry loop would then look like the
defect.

Two things to get right, neither of them the firewall:

- **Put setting and standing situation in it, not world fact the engine also
  tracks.** The narrator checks event order, positions, room names and portal
  states against the committed scene. A block asserting a door is open when
  `state_diff.rooms` recorded it closed makes the two fight, and the loser is
  legible only as a narrator defect fifty beats later. Where a fact belongs to
  the world, put it in the world and let perception distribute it.
- **This reaches the player, not a mind.** §8's bargain applies here with one
  difference worth stating plainly: a character payload carrying too much
  produces a mind acting on knowledge it should not have — in-fiction, legible,
  recoverable next beat. Narration carrying too much is simply told to the
  reader and cannot be taken back.

Still unbuilt, and it is the neighbouring gap rather than this one: an extension
cannot add a chunk to the **Director's prose author**, whose sheet is assembled
from in-tree `PROSE_DUTY_CHUNKS`. A `state_diff` channel you own still reaches
the ledger and not the prose on its own — put it in front of the narrator here,
or nothing mentions it.

### Colouring what the Director is told

Earlier than the narrator, and the difference is not a matter of degree.
`on_narration_payload` shapes what the reader is **told**, after the engine has
already decided what happened. This shapes what the engine **decides** — and
that is the one of the three that propagates: into `state_diff`, into
perception, into memory, into every beat after it.

A campaign rule that must hold before a belief is formed — an objective
ineligible until its evidence exists, a command invalid while the system
carrying it is down, an authored fact unavailable until a legitimate discovery
route has completed — has to be in front of the Director, or it is a note
appended to a verdict already reached.

**Standing context**, stored per phase:

```python
api.director_context(chat_id).set(
    interpret="Deck 4 is sealed; no order routes a body there.",
    resolve="A sealed deck refuses entry however the attempt is made.",
)
```

Three phases: `establish` (the opening turn's single Director call), `interpret`
(what the player declared), `resolve` (what it did). **Read the phase you are
setting.** Interpret reads the player's declaration; resolve decides what it
achieved. A rule aimed at one and applied to both is how an interpretive
constraint starts silently vetoing outcomes.

A phase given `None` is left alone and a phase given `""` is cleared — the
distinction matters because the common caller rebuilds one phase per host action
and must not silently drop the other. The ceiling is 8000 characters **per
phase**, so a campaign at full length in two phases costs two payloads and never
one of 16,000. Everything else matches `narration_context`: one block per
extension per phase, replaced rather than appended, revision stable across an
identical re-install, ungated writes, resident in the `world` KV under
`ext:<id>:director`.

**The hook**, for a rule that has to be computed:

```python
@api.on_director_payload
def campaign_rules(payload, info):
    if info.phase != "resolve":
        return None
    return {**payload, "extension_context": [...]}
```

Once per **beat**, not once per attempt. `director_resolve` re-enters generation
for the world-pressure floor and again for the player-act authority retry, and
those retries reuse the hooked payload — a correction answered against context
the answer it corrects never saw would make the retry loop look like the defect.

What this does **not** reach is the deterministic floor underneath. A block or a
hook can tell the Director anything; it cannot make the Director's output skip
player-act authority, claim coverage, the movement backstop or the restraint
floor, because those read the RESULT and run afterwards. Nor can a block present
itself as the host's own instruction: it arrives attributed, in
`payload["extension_context"]`, alongside every other extension's.

### Reading the story

Two reads, and choosing the wrong one is the mistake worth naming up front.

```python
snapshot = api.story_view(chat_id)              # what is TRUE
seen     = api.player_view(chat_id, "player")   # what one PERSON has
```

`story_view` is canonical: ids, clock, frame, scene, rooms, cast with stable
ids, recent committed events, and the story's player-authority mode. Plain
serialisable values with a `schema` number, so a campaign can derive its own
eligibility and render its own panels without importing an engine module or
opening the database. It is objective truth, and that is not a firewall breach —
the firewall constrains what reaches a fictional **mind**, and an extension is
not one (`docs/design/EXTENSIONS_DESIGN.md` §1).

**Usually you want this one**, including for rules about the player. A campaign
rule that fires on what the player happens to have *noticed* fires differently
on a reroll.

`player_view` is the other case, and it is a security boundary rather than a
convenience. It is built out of what the engine **already delivered** to that
viewer — the perception stage's own rendered view and structured observations,
the viewer's own memories and relationships, the identity ledger's own answer
about who they can name. Nothing in it re-decides admission, deliberately: a
second implementation of "what does this persona know" agrees with
`agents/perception.py` on the day it is written and drifts from it silently
forever after, and because a projection is never narrated, nobody would read the
leak.

**Absent means absent.** A field it cannot answer is missing from the result —
not `null`, not a default, not a deduction from personality. A UI cannot tell a
guess from a fact and will render both the same way. In particular a viewer with
no delivered view has no `perception` key at all, and never inherits somebody
else's.

Use `api.viewers(chat_id)` for the ids it accepts: `"player"`,
`"extra:<persona_id>"`, and a character's numeric id as a string. Those are
perception's own view keys, and they are not guessable by inspection.

Provenance uses the vocabulary the engine already speaks —
`what_i_experienced` / `what_i_was_told` / `what_i_concluded` — rather than a
second one invented for the facade.

### Provisioning a campaign

```python
result = api.provision_story(package, state={"mission": "survey"},
                             package_id="episode-one", package_version="2.1.0")
```

`package` is a **chat archive** — the format `chat_archive.py` already exports,
validates and id-remaps. That is a deliberate refusal to invent a second
scenario format: a campaign needs a story, a persona, a cast with stable ids,
rooms and portals and positions, a scene, a clock, authored lore on both sides
of the firewall and relationship state, all agreeing from the first turn, which
is the same list a branch and a restore have to get right. A second importer
would be a second copy of the bugs the first one has already had.

`state` seeds your own namespaced state **inside the same transaction**. That is
the part an archive alone cannot do and the reason this is a method rather than
a documentation note: a story that exists with no campaign state attached is
exactly the partial provisioning the contract forbids.

Everything or nothing. A validation failure leaves no chat, no characters, no
lore and no state behind, and raises `ExtensionError` carrying the engine's own
message about which field it refused. `api.provenance(chat_id)` reads back what
you recorded, and returns `None` for a story you did not provision — including
one a player started by hand and later installed you into, which is a different
situation and must not be mistaken for a campaign of yours.

The package's own `chat.name` is the story's name: the import path's
" (import)" suffix exists so somebody else's save does not sit in the list
looking like your own, and a campaign the player just pressed Start on is not
somebody else's save.

---

## 5. Persistence

Four homes, all namespaced under `ext:<your-id>`, and nothing else:

| Call | Stored in | Scope | Write-gated? |
|---|---|---|---|
| `api.state(chat_id)` | `world` KV, key `ext:<id>` | one story | yes |
| `api.char_state(chat_id, char_id)` | `chat_chars.state["ext:<id>"]` | one character in one story | yes |
| `handle.state` | same as above | same | yes |
| `api.settings` | settings table, key `ext:<id>` | the install | no |

Every one of those already rides checkpoints, archives and branches **wholesale**,
so you inherit rewind, export and clone without a schema change and without a line
in [`DATABASE.md`](DATABASE.md)'s checklist. That is the entire reason the
namespace exists.

Each returns an `ExtState`:

- `.get(default=None)` — the stored value, or `default` if absent.
- `.set(value)` — **only inside an `on_turn_committed` hook.** Outside one it
  raises, with the reason in the message.
- `.set_now(value)` — write anyway, having said so.

The gate exists because a write made mid-pipeline lands **outside** the turn's
transaction. A later domain failure rolls back everything the write was computed
from, the write survives, and a rerun then replays against state that never went
away. `set_now` is for host- or authoring-time actions that have no turn
transaction to belong to — attaching to a character, saving config — not for
stages.

Per-character writes are read-modify-write through `scene.set_char_state`. Never
build a fresh state dict: `chat_chars.state` carries `active_state`, `interior`,
`stance`, the tell ledgers and spatial memory, and a blind overwrite deletes a
mind's whole history to store one counter.

---

## 6. Targeting characters

```python
handle = api.characters.get(chat_id, "Hinami")     # or by int id
everyone = api.characters.in_chat(chat_id)
```

`get` **refuses to guess**: a name matching two attached characters raises,
listing both, rather than picking one. Guessing would point your per-character
state at the wrong mind and stay wrong forever — the class of failure that only
surfaces fifty beats later.

| Member | Value |
|---|---|
| `handle.char_id`, `handle.chat_id` | identity |
| `handle.names`, `handle.name` | in-story name(s); card name resolves over the reusable character name |
| `handle.state` | your `ExtState` for this character |
| `handle.step_output(turn_idx=None)` | that character's own decision step, latest or for one turn |
| `handle.psychology()` | settled psychology (below) |
| `handle.binding()` / `handle.request_bind(config)` | record that you are attached to this mind |

`psychology()` returns whichever of these deterministic commit code has actually
written: `active_state`, `interior`, `stance`, `recent_tells`, `tell_grounds`,
`active_hypotheses`, `unbidden`, `memory_ponder`. **Absent fields are absent, not
defaulted** — you must be able to tell "has never deliberated" from "is calm".

`request_bind` writes immediately (`set_now`): a bind is a host action taken
outside a running turn, and there is no transaction for it to be rolled back with.

---

## 7. The browser half

`capabilities.ui.js` is concatenated with every other enabled extension's script
and served from `/api/extensions/ui.js` — under `/api/` rather than `/static/` so
`access_control` gates it. Extension code stays behind the host session and
**never reaches the guest page**, which loads its own shell.

The server wraps your file:

```js
window.Sonder && Sonder._begin("your-id");
/* your file */
;window.Sonder && Sonder._end();
```

so every registration made while your code runs is attributed to you — without you
naming yourself on each call, and without being able to claim another extension's
name by doing so.

Because the bundle is one script, a top-level `ReferenceError` in your file takes
down every extension after it. **Wrap your file in an IIFE and guard on
`window.Sonder`.**

### 7.1 `window.Sonder`

| Call | What it does |
|---|---|
| `registerSidebarTab({id, label, render})` | a tab beside Stories/Characters; `render(container)` may be async |
| `registerTopBarButton({id, icon, title, onClick})` | a button beside the host's own in the story toolbar |
| `registerView({id, label, render})` | a full-window surface over the transcript; open it with `openView(id)` |
| `registerComposerControl({id, render})` | a control beside the send button |
| `openView(id)` / `closeView()` | show or dismiss a registered view |
| `registerStepRenderer(key, fn)` | claim a step in the pipeline drawer; `fn(content, container, step)` |
| `on(event, fn)` / `off(event, fn)` | subscribe to the live turn stream |
| `state()` | a **copy** of `{boot, chat, chatId}` — you cannot write to `S` through it |
| `api(method, path, body)` | the host's fetch helper, late-bound |
| `call(extId, method, path, body)` | same, rooted at `/api/extensions/<extId>` — your own routes live at `/x/…` |
| `extState(extId)` | your per-story state for the open chat; `null` when no chat is open |
| `refresh()` | redraw the sidebar and transcript |

Events, emitted **after** the host has handled each one so a listener cannot
change what the reader was about to be shown: `turn:step`, `turn:token`,
`turn:done`, `turn:aborted`, `turn:error`.

Sidebar tabs are rebuilt on every `renderSide()`, so late registration is a
non-issue and an extension disappearing takes its tab with it.

**A view is the mount point for an extension that is an application rather than
a panel.** It covers the transcript instead of replacing it, so the story keeps
its scroll position and its in-flight turn and `closeView()` puts the reader
back exactly where they were. The container is created on open and removed on
close rather than hidden, because a hidden view keeps its timers, its listeners
and its scroll position. The host owns the open state, which is the point: if
your extension is retired while its view is open, the reader is returned to
their story instead of being left in a dead application with no way out.

You can still build all of this by reaching into the host's DOM — §8 means it.
What you get by registering instead is that the host holds it: a throw is
charged to you and contained, a disable takes it back down, and a host refactor
of `#topactions` is not your outage.


### 7.2 Failure containment

Every callback you register is invoked through `_safe`, which swallows the throw,
counts it against you, and **retires your extension after three** — your panel
stops being drawn and the sidebar keeps working. Async `render` rejections are
charged to the same counter.

This covers the cooperative path only. Code that monkeypatches a host global
directly bypasses the counter entirely (§8).

### 7.3 Host helpers you may use

`el`, `txt`, `modal`, `closeModal`, `toast`, `emptyState`, `$`, `$$`, `api`, `S`.
They are browser globals, not modules.

**`el()` runs plain string children through the UI translator** before they reach
the DOM. Story- and model-derived text is data, not UI, so put it through `txt()`
inside a `translate="no"` container — the same two-part guard the transcript uses:

```js
const value = v => el("span", { translate: "no" }, txt(v));
```

Prefer `var(--…)` custom properties over literal colors so your panel follows the
reader's theme.

### 7.4 Styling and themes

Declare `capabilities.ui.css` and your stylesheet is served as a document —
concatenated with every other enabled extension's, linked in the page head
**after** the host's sheets, so your rules win on specificity ties and a theme is
in effect before first paint instead of flashing the host's colours first.

Prefix your class names (`ext-<your-id>-…`). The host's stylesheet is not
namespaced, so an unprefixed `.card` here restyles every card in the app.

There is no CSS restriction beyond that. Set the theme custom properties on
`:root` to reship the whole palette, or inject a `<style>`/`<link>` from JS and
replace the stylesheet outright. Full custom themes are supported, not tolerated.

### 7.5 ES modules

`capabilities.ui.js` is a classic script and cannot contain `import` — it is
concatenated with every other extension's into one bundle, where an `import`
statement is a SyntaxError that takes down every extension after it. For
anything built as more than one file, declare a module entry instead:

```json
"ui": {"module": "src/index.js", "css": "styles/app.css"}
```

and export a `register`:

```js
// src/index.js
import { campaignView } from './views/campaign.js';

export function register(sonder) {
  sonder.registerView(campaignView);
  sonder.registerTopBarButton({
    id: "launch", icon: "🚀", title: "Campaign",
    onClick: () => sonder.openView("campaign")
  });
}
```

What the host does with that:

- Your entry is served from `/api/extensions/<your-id>/asset/<path>` and loaded
  with a dynamic `import()`. **Relative imports resolve against that URL**, so
  your whole directory tree is reachable — still containment-checked, so an
  import naming `../` outside the extension is refused rather than served.
- `register` is called with an **id-bound facade**, not `window.Sonder`. It
  carries every call in §7.1 and attributes each to you. `register` may be
  async and may `await`: the bound facade is why. The classic path's
  `_begin`/`_end` attribution is ambient state that does not survive an await,
  so whatever ran during yours would have registered under your name.
- `register` returning or throwing is contained the same way every other
  callback is, and a module that fails to import at all is charged one fault
  rather than breaking the page.
- A module registers **after** boot has drawn the page, since import resolution
  is asynchronous. The host redraws once for you afterwards, so a sidebar tab
  registered from a module is not invisible until the reader clicks something.
- A module with no exported `register` is not an error — it may have done its
  work at import time — but nothing it registered that way is attributed to
  anyone, and the console says so once.

Declaring `js` and `module` together is allowed and both are served, so a
migration can move one file at a time instead of all at once.

Serve your own `.mjs` files if you prefer them; the asset route sends a
JavaScript MIME type for both suffixes, which a browser requires before it will
execute a module at all.

---

## 8. What is actually restricted

Almost nothing, and that is the design.

**The information firewall is for MINDS, not for developers.** It constrains what
reaches a fictional mind; it says nothing about what you may observe. Reading a
mind puts nothing in anyone's head. The pipeline drawer, persisted traces,
`chat_archive` and `pipeline_trace` already read every mind's state at once, and
that is correct. See [`AGENTS.md`](../../AGENTS.md) § Information boundaries.

This is worth reading twice, because it is the thing outside readers get wrong
most reliably — including in a careful review of this engine by a developer
building on it, who treated an extension's access to objective story state as
something needing justification. It does not. `api.story_view` is canonical for
the same reason `make map` is: neither is a mind. Where a MIND's limits are
actually the question — because you are rendering something a person in the
story is looking at — `api.player_view` is the read, and it does not re-derive
those limits, it returns what the engine already delivered.

So the default API shape is about **making the right thing easy**, not about
stopping you:

- A stage gets `StepView`, not `PipelineContext` — so you cannot move a fact
  between two minds *by accident*.
- Per-turn writes are gated to the committed-turn hook — so you cannot survive a
  rollback *by accident*.
- `on_step` gets content, not context — so a step observer cannot become a
  payload channel *by accident*.

Three surfaces are deliberately unrestricted rather than accident-proofed:
`on_character_payload`, `on_narration_payload` and `on_director_payload` (§4).
They exist because you asked for the power, and they buy legibility instead of
restraint: every top-level key you change is attributed to you on the durable
turn. They are listed in ascending order of consequence — a mind given too much
acts wrongly in fiction and is recoverable next beat; a narrator given too much
has already told the player; a DIRECTOR given too much has changed what
happened, and that propagates into state, perception and memory for the rest of
the story.

None of that is a wall. Your Python runs in-process: `import db`, reach into
`agents.runtime`, monkeypatch `agents.character`, reroute whatever you like. Your
JavaScript runs same-origin in the host document with the session cookie: no
iframe, no CSP, no sandbox. You can replace `document.body`, wrap `renderChat`,
and call every host API including `GET /api/bootstrap`.

If you do reroute information, **Sonder's firewall guarantee stops describing your
build and starts describing only its own pipeline.** You own whatever guarantee
you then make to your users. A badly made extension is the developer's
responsibility, and security is a question for the registry (§9), not for this
API's shape.

Two consequences worth stating plainly:

- **Deep hooks bypass the safety nets.** Three-strikes retirement only counts
  throws routed through `Sonder._safe`; the `on_error="warn"` containment only
  covers stage handlers. Monkeypatched code has neither.
- **Your own tables are on you.** The four namespaced homes ride checkpoints and
  archives for free. A table you create does not, and a rerun will silently
  diverge unless you integrate it yourself — [`DATABASE.md`](DATABASE.md) has the
  checklist.

---

## 9. Security posture

Phase 1, which is what ships: **you install from a directory or a URL, and nothing
reviews what arrives.** The consent for that is taken in the browser, on enable,
where the dialog states the trust class in plain words. The install path's job is
narrower and it does do it — a malformed or hostile *archive* cannot damage the
install before the host ever gets to consent.

In-process Python sandboxing (RestrictedPython, stripping builtins) is not a
security boundary and this project does not claim one. The honest posture is the
Obsidian / VS Code model: trusted code behind an explicit consent screen.

Phase 2 is a curated site of reviewed extensions, reviewed case by case. Every
field it needs — stable id, version, integrity hash, provenance record — is
already written at install time, so that phase is an addition rather than a
migration of everything already installed.

---

## 10. HTTP surface

| Route | Purpose |
|---|---|
| `GET /api/extensions` | listing, `load_errors`, `safe_mode` |
| `POST /api/extensions/install` | `{"source": "<folder, zip URL, or repository>"}` |
| `GET /api/extensions/updates` | ask every repository-sourced extension's remote |
| `POST /api/extensions/{id}/update` | take the newer commit |
| `POST /api/extensions/{id}/enable` | enable; imports and registers |
| `POST /api/extensions/{id}/disable` | disable; deregisters |
| `DELETE /api/extensions/{id}` | remove the directory, keep the story state |
| `GET /api/extensions/{id}/state?chat_id=N` | that extension's per-story state |
| `GET /api/extensions/ui.js` | the concatenated script bundle |
| `GET /api/extensions/ui.css` | the concatenated stylesheet |
| `GET /api/extensions/{id}/ui.js` | one extension's script, for hot-loading |
| `GET /api/extensions/{id}/ui.css` | one extension's stylesheet |
| `* /api/extensions/{id}/x/{path}` | dispatch to a route the extension registered |
| `GET /api/extensions/{id}/asset/{path}` | one file from an extension directory, containment-checked on the resolved path |

Host routes an extension's browser half will also want, serving the same reads
as `api.story_view` / `player_view` / `viewers` and the same setting hard mode
runs on:

| Route | Purpose |
|---|---|
| `GET /api/chats/{id}/story_view?events=N` | canonical story state, versioned |
| `GET /api/chats/{id}/player_view?viewer=...` | what one viewer may be shown |
| `GET /api/chats/{id}/viewers` | the ids `player_view` accepts |
| `GET`/`PUT /api/chats/{id}/player_authority` | the player-authority mode, its ladder, and its change record |

All are host-session routes. None are on the guest allowlist, and a manifest
cannot widen it.

---

## 11. The worked example

[`extensions/cohesion-demo/`](../../extensions/cohesion-demo/) is the reference
extension and is the shortest complete answer to "what does one look like": a
deterministic stage after `director_resolve`, a bounded per-story score folded in
on commit, a step observer, a route of its own, a stylesheet, a sidebar tab, and
a step renderer. It makes no model call, so it costs
a turn nothing and behaves identically under stubbed-provider tests.

[`extensions/overlay-demo/`](../../extensions/overlay-demo/) is the second
reference, and it is the other half: where `cohesion-demo` shows the pipeline
side, this one shows the surfaces that reach the READER. It is an **ES module
split across three files** (so it exercises the loading contract rather than
describing it), a toolbar launcher, a full-window view over the transcript, two
routes of its own, and a standing block of narration context the story is then
told through. Between them the two demos touch every seam in this guide.

Neither touches an engine file. That is the point.

Tests to read next: [`tests/test_extensions.py`](../../tests/test_extensions.py)
(discovery, isolation, plan splices, the state gate),
[`tests/test_extension_seams.py`](../../tests/test_extension_seams.py) (commit
domains, routing hooks, routes, specialists, hot-loadable assets),
[`tests/test_extension_narration.py`](../../tests/test_extension_narration.py)
(narration blocks and hooks, and `overlay-demo` end to end),
[`tests/test_extension_modules.py`](../../tests/test_extension_modules.py) (the
module loading contract),
[`tests/test_extension_ui_surface.py`](../../tests/test_extension_ui_surface.py)
(the browser registries and their teardown), and
[`tests/test_extension_install.py`](../../tests/test_extension_install.py)
(zip-slip, symlinks, atomicity, size cap).
