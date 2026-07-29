# Findings — The Drowned Hare

Ten turns, one room, two characters, nothing dramatic. Run on the 6.1 dev
tree (`b41053d`) to check in live play what the 6.0.1–6.1 fixes had only been
shown to do in tests.

**Why an inn and not a maze.** Every defect fixed across 6.0.1–6.1 came out
of ordinary conversation, not navigation: repeated dialogue, a contact ledger
that never retired anything, a mind pinned at saturation, inference memories
crushed to a floor. `docs/OPEN_ITEMS.md` already recorded that the maze arms
were saturated and had stopped producing findings. A quiet room is the
instrument that finds this class of defect, because a character with nothing
new to react to is a character that starts repeating itself.

## Result

10 of 10 turns committed. 104 model calls, **zero failures**. Turn times
84–201s.

### Dialogue — the 6.0.2 repetition work

| Speaker | Lines | Verbatim repeats | Refrain |
|---|---|---|---|
| Corwin Ash | 9 | 0 | none |
| Marta Quill | 14 | 0 | none |
| Ilsabet Vane | 9 | 0 | none |

Measured with the engine's own detectors: `_first_verbatim_repeat` against a
rolling six-line window, and `_self_line_refrain` over each speaker's last six
lines. The refrain check looks for a shared opening or closing word across at
least three of them — the template failure that passes a content check while
reading as a stuck record.

### Memory — the 6.1 reconciliation fix

```
inference   n=13   floored (<=0.09): 0/13   avg confidence 0.374
episodic    n=32   avg confidence 1.000
```

The distribution is the point, not the average. Every row lands in one of the
three intended states:

| State | Confidence | Example claim |
|---|---|---|
| held | ≈ mint | "ready to retire for the night" (formed this turn) |
| live but decayed | between | "curious about connections between patrons" |
| demoted once | ≈ mint × 0.55 | "wet traveller who wants heat and is not particular" |

Lowest value in the whole story is **0.275**. Nothing reaches the 0.08 floor;
nothing compounds. For contrast, the two live stories played on the broken rule
sat at **76% and 80% of inference rows on the floor** within 7 and 18 turns.

Worth noting *which* claims were demoted: transient reads of a stranger — that
he is wet, that he wants heat, that he is curious about the inn. A character
does stop actively holding those once the man is warm and the conversation has
moved on. Demoting them is right. Crushing them out of retrieval was not.

### Contacts — the 6.0.2 ageing work

0 standing at the end. **Not exercised rather than passed**: nobody touched
anybody across ten turns of stew and conversation, so the ledger had nothing to
retire. Pre-fix behaviour was monotonic growth toward the 40-record cap, but
this run does not demonstrate the fix either way.

## What this run does not cover

Stated plainly so the pass is not read as broader than it is:

- **Contacts** — see above. Needs a scene with physical contact.
- **Bodiless voices** (6.0.2) — no ship AI or PA system present.
- **Narration-in-speech repair** (6.0.1) — the scripted player inputs were
  cleanly quoted, so the Director never had messy prose to mis-parse.
- **Unbidden recall** (6.1) — the trigger requires a measurably stuck mind.
  Nothing got stuck, which is itself the result, but it means the mechanism
  went unobserved.

## Reproducing

```bash
python "play_turn.py" --dry-run     # build the world, no model calls
python "play_turn.py" --turns 10    # the real run
```

Writes to a scratch database (`/tmp/test-story/story.db` by default) and opens
`engine.db` read-only, solely to carry model routing and provider connections —
the same approach `tools/maze_experiment.py` uses, since a fresh database has
no model configured for any role.

To read the result in the app rather than as a document:

```bash
ENGINE_DB=/tmp/test-story/story.db uvicorn app:app --port 8009 --reload
```
