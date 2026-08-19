# Frame-coherent public reads — design note

Status: **Built.** `api.at_frame` and `ExtensionFrameView` in
`extension_runtime/api.py`; explicit `frame_id` on `web/story_view.py`'s
`story_view`/`player_view` and the api's mirrors of them; `player_view`
reports its `frame`. Tests: `tests/test_extension_frame_view.py` (the
route-level composition proof) and `tests/test_story_view.py`'s
`TestExplicitFrameSelection` / `TestPlayerViewFrameField` /
`TestFrameBoundViewerBudget`. What the surface *does*, field by field, is
[`docs/guides/EXTENSIONS.md`](../guides/EXTENSIONS.md) § Reading the story;
if the two disagree, the guide is right.

This note is the argument: the seven decisions behind the contract, made
against the Directive integrator's P0 finding (mixed-frame projection) and
their proposed `at_frame` sketch — which was a proposal this note evaluates,
not a specification it follows.

---

## The defect, precisely

`web.story_view.player_view()` resolves the latest committed turn ACROSS
frames and holds that turn's frame for the whole view — then resets the
contextvar on exit, correctly. `api.frame_state(chat_id).get()` and
`api.char_state(...).get()` follow `db.active_frame_id`, which an extension
HTTP route has never set, so they answer for the implicit present. One DTO
composed from all three carried the future's scene and identity beside the
present's mission, clock and crew state: structurally valid, semantically
impossible, and worse than a hard failure because every field is
individually plausible. Each API was correct alone; the class of defect is
*composition without a shared frame selection*, so the fix must live where
the composition happens.

## 1. Facade, parameters, or both — both, with distinct jobs

`api.at_frame(chat_id, frame_id=...)` returns an immutable
`ExtensionFrameView` binding `story_view`, `player_view`, `frame_state` and
`char_state` to ONE resolved frame. The reviewer's argument for a facade is
accepted because it matches how the defect happened: a per-call `frame_id`
parameter must be remembered on every read a growing DTO adds, forever, and
the defect was precisely a call that had nothing to remember it *with*. The
facade resolves once, is inspectable (`view.frame_id`, so a test or log can
prove what a request read), and cannot drift.

The explicit `frame_id` parameters on `story_view`/`player_view` exist
anyway, for two reasons: the facade needs them (without them it would
re-resolve "latest" per call, which is the drift it exists to prevent), and
a single-read caller should not have to build a coordination object to ask
one question. The guide points composed reads at the facade.

## 2. Omitted means latest; `None` means the present — and why that is not a trap

Omitted `frame_id` resolves the latest committed turn's frame, once:
"whatever frame the story is actually on", the behaviour the views already
had. Explicit `None` selects the implicit present era.

`None`-as-present would be a trap in most systems. Here it is the engine's
own vocabulary: `turns.frame_id IS NULL` *is* the present, `active_frame_id`
defaults to `None`, `frames.get_frame(None)` synthesises the present frame.
Spelling the present any other way (`"present"`, a magic integer) would
create a second vocabulary that every boundary — checkpoints, archives,
branch remapping — would have to translate at. The cost is that "omitted"
and "`None`" must be distinguishable, so both `web/story_view.py` and
`extension_runtime/api.py` carry a module-private sentinel default. The two
sentinels are deliberately different objects: neither module's private
marker may ever travel into the other as a value.

One pre-existing collision is documented rather than repaired:
`story_view.latest_turn(chat_id, frame_id=None)` spells "across all frames"
with the same `None`. The view functions never pass `None` through it — an
explicit frame goes through `_turn_in_frame`, whose `IS ?` matches the
present's `NULL` turns — and its docstring now names the collision.

## 3. Empty stories and empty frames

- **A chat with no turns at all** stands in the present: omitted resolves to
  `frame_id=None`, `turn: None`. A story that has not started has not gone
  anywhere else.
- **A selected frame that exists but holds no turns** is honoured, never
  silently fallen back from: its views report `turn: None` beside that
  frame's own state, because frame state legitimately exists before any turn
  runs in the era (`provision_story` seeds `frame_state`; a fallback would
  make provisioned state unreadable until the first beat).
- **A frame that does not exist, and a frame belonging to another chat, get
  one identical refusal** (`ExtensionError` at the api, `ValueError` at the
  web layer): an extension holding chat A must not be able to use the
  refusal text to probe which frame ids exist in chat B.

## 4. Writes bind exactly like reads

Decided FOR bound writes, against the instinct that reads are safe and
writes are scary, because a read-only facade would *manufacture* the write
half of the same defect: read era A through the view, compute, then write
through the only remaining channel — ambient `api.frame_state(...).set_now`
— which lands in era B. Read-modify-write must land where it read.

What makes this safe to grant:

- **Frames are concurrent eras, not read-only snapshots.** The engine's own
  model (`core/frames.py`) supports simultaneous play eras apart; a
  non-present frame is a live storage home, and `db.wset_for_frame` is the
  primitive engine code (spatial split/merge) already uses to write a frame
  other than the ambient one. The facade adds no new power, only a public
  spelling of an existing one.
- **The blast radius is the extension's own namespace.** The facade reaches
  `extf:<id>` world rows and the `ext:<id>` key inside character state —
  never the scene, the ledgers, or another extension's rows. Corrupting a
  *story* through it is not reachable; corrupting your own campaign state
  in the wrong era was already possible ambiently and is now harder.
- **The commit gate is unchanged.** The binding decides WHERE a write
  lands; the gate still decides WHEN it may: `set()` only inside an
  `on_turn_committed` hook, `set_now()` the named escape hatch. A bound
  facade is not a bypass, and `tests/test_extension_frame_view.py` pins the
  gate firing through it. Inside a commit scope a bound write joins the
  turn's transaction like any other, so it rolls back with the beat.

## 5. A bound read survives an ambient frame change — without leaking

The reviewer required that a bound `ExtState.get()` called after something
else moved `active_frame_id` still answer for the captured frame, and
recommended NOT leaving the contextvar set across extension code. Both
hold, by construction: bound world state closes over
`wget_for_frame`/`wset_for_frame`, which set-and-reset the contextvar
around one query; bound character state resolves the frame into the SQL
parameter and into `set_char_state(frame_id=...)`. Nothing ambient
survives a call, and the pinning test asserts both the answer and the
untouched contextvar. The unbound `api.frame_state`/`api.char_state`
keep ambient resolution *at call time* — byte-identical behaviour, which
pipeline code (where the ambient frame IS the answer) depends on.

## 6. Events are story-global, and the facade must not imply otherwise

`world_events` is the objective record; the frame machinery is an epistemic
cursor over one story, not a partition of its truth — entities, conditions
and scheduled events are chat-global too, and `core/frames.py` calls that
slicing real follow-on work, not attempted. So `story_view.events` reports
the whole ledger's tail under ANY frame selection, the ruling is written on
`_events` itself (with an explicit "do not quietly add a frame filter
here"), and a consumer wanting one era's events filters on `turn_id`
knowingly. Pinned by `test_events_stay_story_global_under_any_selection`.

## 7. `player_view` reports its frame; no schema bump

`player_view` now carries `frame` exactly as `story_view` does (`None` =
the present), so coherence across composed reads is *observable* — the
route test's `assert player["frame"]["id"] == host.frame_id` is the
consumer-side proof the reviewer asked to be possible.

No `STORY_VIEW_SCHEMA` bump, and the distinction from the schema-2 `people`
bump is the argument: `people` collided with "absent means absent" (after
the change, an omitted key meant "empty roster", so absence changed meaning
and only a version could disambiguate). `frame` is ALWAYS present once the
field exists — `None` is the present's identifier, not a default — so an
absent key still unambiguously means "engine predates the field", and the
key itself is the capability check. The reasoning is recorded beside the
constant in `web/story_view.py`.

## Two repairs the contract forced inside `web/story_view.py`

Making views frame-selectable exposed two reads in the module that were
themselves quiet members of the mixed-frame class, and the firewall
constraint (a frame-bound read must not widen what a viewer can reach)
required fixing them at their source:

- `_viewer_memories` was the sixth raw `memories` read beside the five
  `mind/memory.visible_memory_rows` consolidated — it had reproduced the
  `char_id` filter and forgotten the frame filter, exactly the drift that
  seam's comment predicts. A view bound to a past era handed its consumer
  the character's future-era memories. It now goes through the seam, with
  `before_turn_idx=None` (a projection is a host browsing, not a mind
  deciding a beat).
- The `relationships` read went straight to `chat_chars` — the present's
  row — under a held frame. It now reads the `chat_char_frames` overlay
  first, like the pipeline's own reads of a portrayed mind.

## Refused

- **Binding `api.state`, `api.documents`, `api.settings`, or `viewers` to
  the facade.** Chat-global (or install-global) by design; putting them on
  a frame-bound object would imply a scoping they do not have, which is the
  mirror image of the original defect.
- **Binding extension route dispatch to a frame ambiently** (the reviewer's
  alternative fix). It would repair the route path by the exact mechanism
  — an ambient contextvar spanning arbitrary extension code — the facade
  exists to avoid, and would leave non-route compositions (hooks, jobs)
  unrepaired.
- **Frame-filtering `story_view.events`** — decision 6.
- **A `frame_explicit_reads` capability flag.** Discovery is the review's
  separate P2; the observable `frame` field and `at_frame`'s existence are
  probe-able without one, and a capability registry deserves its own
  design rather than a one-off boolean here.
- **A read-transaction/snapshot token** (the review's "atomic read
  snapshot" hardening). Frame coherence and point-in-time coherence are
  different axes; SQLite-level snapshot reads across multiple public calls
  are real follow-on work and are not smuggled in under this contract.
