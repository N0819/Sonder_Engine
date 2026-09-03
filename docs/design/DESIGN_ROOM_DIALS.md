# Giving the Writers' Room authority over the dials

**Status:** argument, not built. Written 2026-09-04 after the config-authority
audit, when the owner asked how *all* of the story's configuration might become
the room's rather than a menu's.

## 1. The rule that decides ownership, and why it is not a preference

The engine already answered this and wrote the answer down; nothing here needs
inventing.

A value that is **preserved across a restore and a branch** is the host's.
`persist/checkpoints.py`'s `PRESERVED_SETTING_KEYS` is the operational form:
those keys survive a rewind precisely because nothing in the fiction depends on
which pacing you prefer, and a reroll is supposed to re-run the beat rather
than reset your preferences. Room authority is the exact inverse *by
construction*: mandates and packages ride frame-scoped rows, so a rewind unsays
them and two branches disagree.

So the question is never "would an author decide this?" It is:

> **If a rewind that undoes the beat should also undo this value, it is
> authored. If it should not, it is configuration.**

That is why the four fields retired from the style guide on 2026-09-04 could
go — genre, director notes and mapping notes were standing instructions a plan
can carry — and why `tone` and `avoid` stayed: deterministic code reads them
(the backdrop prompt and key, the acoustic fingerprint, the image's veto
clause) and nothing routes a conversation into an image prompt.

## 2. Why the obvious approach cannot work

The obvious approach is a package operation that writes the world key. It
fails on three counts, and the third is fatal.

- **The blob is replaced, not merged.** `PUT /api/chats/{id}/style_guide`
  replaces the whole guide, and `background_config`'s sole writer replaces the
  blob holding the host's two cost caps. An operation that wrote a dial would
  have to round-trip every field it did not mean to touch, and a field omitted
  is a field silently deleted.
- **The scopes disagree.** `style_guide`, `dialogue_config`,
  `background_config` and `promotion_thresholds` are chat-global;
  `room_mandates` and `plot_packages` are in `FRAME_SCOPED_WORLD_KEYS`. A room
  seated in one era would move a dial in every branch at once.
- **There is no honest provenance to record.** The taxonomy has exactly three
  tags — `SET_BY_HAND`, `DETECTED`, `MACHINE_MINTED` — and none of them means
  "written by an authoring agent". Tag a room-set value `SET_BY_HAND` and it
  outlives the rewind that was supposed to undo the package that wrote it;
  leave it untagged and it evaporates on the host's next reroll. **Both are
  wrong, and no fourth tag fixes it**, because the value's correct lifetime is
  not a property of the *setting* at all. It is the lifetime of the package.

## 3. The answer: an overlay, which is what this engine already does

Every time this codebase has faced *two authors and one value*, it has refused
the shared mutable field and resolved an overlay at read:

| the library's | the story's | resolved by |
|---|---|---|
| `characters.sheet` | `chat_chars.sheet` | `COALESCE(cc.sheet, ch.sheet)`, in all ten readers |
| a library lore entry | `lore_overlays` | `set_lore_overlay`, refused on a book the story owns |
| `chat_chars` | `chat_char_frames` | the per-frame override, so a character can differ between eras |

The dials want the same shape and for the same reason. **The host's value is
never touched.** A room-set dial is an entry in a frame-scoped `config_overlays`
key:

```
config_overlays = {
  "style_guide.tone": {
    "value": "wry, unhurried",
    "package": "pkg_7f2…",      # what authored it
    "mandate": "mnd_3a…",       # what permitted it
    "turn_idx": 412,
    "why": "the harbour chapters read colder than the story wants",
  },
}
```

and one accessor per config family resolves `overlay(key)` before the stored
blob. That is four small edits — `style_guide`, `dialogue_config`,
`background_config`, `promotion_config` — and no change at any of the dozens of
call sites downstream.

Every blocker in §2 dissolves rather than being worked around:

- **Provenance** — the overlay *is* the record, and it says which package and
  which mandate. The host's own value stays `SET_BY_HAND` and stays preserved,
  because nothing wrote over it.
- **Lifetime** — the overlay lives in a frame-scoped world key, so it
  checkpoints, branches and rolls back exactly like the package that authored
  it. Revoking is a delete, and the host's dial is *already* the value
  underneath. No migration, no restore path, nothing to get wrong.
- **The blob hazard** — per-key entries, so nothing round-trips a field it did
  not mean to touch.
- **A story with no room** — no overlays exist, every accessor returns the
  stored blob, and the engine behaves exactly as it does today. This is the
  property that lets the whole thing ship dark.

## 4. What each dial needs, and the two that stay refused

The mechanism carries any dial. What differs is the grant.

**Free under an ordinary planning mandate.** The register and the veto (`tone`,
`avoid`), the narration tense, the day length and opening hour, the weather
severity below `catastrophic`, and scene liveliness between `off` and
`ambient`. Each is an authoring read of the story with no consent question and
no unbounded spend.

**Granted per dial, in the player's own words.** Anything with a spend or a
behaviour tail the host would notice on the bill: the autonomy dial and the
call budgets it derives, `max_reactors`, `max_offscreen_actors`,
`max_managed`, and the off-screen cognition toggle. The mandate machinery
already records grants as sentences and cites them back; a dial grant is the
same thing with the dial named.

**Refused, and this is not a mechanism gap.** Two classes stay the host's
however the room asks:

- **Consent over irreversible cast.** `auto_promote`,
  `promote_after_addressed`, `promotion_thresholds.auto_dialogue`. Minting a
  permanent mind is not undone by revoking a mandate.
- **Anything whose failure would be a firewall failure or real harm.**
  `scene_life: full` (it relaxes an information rule, and by the standing
  invariant a leak must be an engine failure rather than a model's),
  `schedule_harm`, `weather_severity: catastrophic`.

The story language stays the host's too, for a duller reason: its route
refuses to run mid-turn and its loss is not recoverable.

## 5. What the host sees

A dial the room has set renders with its host value struck through, the room's
value beside it, the sentence the room gave for it, and one control that
deletes the overlay. That is the whole revert story, because deleting an
overlay restores a value that was never overwritten.

The room's own thread already carries the argument, so the panel does not need
to re-explain it — the dial links to the message.

## 6. Build order

1. **Fix the reversibility defect a dial op would inherit.** `structures` and
   `planned_entities` are absent from `FRAME_SCOPED_WORLD_KEYS` while
   `plot_packages` is in it, so a plan published in one era is held by every
   era and survives a rewind past the package that authored it. A dial
   operation built on that foundation would be wrong in the same way, and the
   bug is worth fixing on its own.
2. **`config_overlays` and the four accessors.** Deterministic, testable with
   no model, and inert until something writes an overlay.
3. **`set_dial` in `OPERATIONS`**, with the usual `shape`/`preview`/`apply`
   triple over an allow-list, modelled on `charter_shock` — the one existing
   operation that writes a dial, and the one that already names a target,
   records a cause and refuses in code.
4. **A `dials` capability in `MANDATE_CAPABILITIES`**, whose closed vocabulary
   currently has no word for this at all.
5. **The panel's overlay affordance**, and `inspect_config` reporting which
   dials are overlaid and by what.

## 7. What this does not solve

The room still cannot see the *consequence* of a dial it sets, because nothing
replays a beat under two settings. A proposal to change pacing is an argument
from reading, not from measurement, and should be presented as one.

And the room is not the only author here: an extension can provision a story
with `offscreen_life` set, and a chat archive carries settings across installs.
Both write the stored blob, so both sit *under* an overlay — which is correct,
and worth a test rather than a comment.
