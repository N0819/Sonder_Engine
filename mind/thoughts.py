"""A mind keeps its thinking for a few turns (the owner, 2026-10-05).

"I was also thinking of maybe preserving the reasoning block in context for
about 5 turns, but it should be chronologically ordered with recent
episodes." And on candour with the mind itself: "we should also probably be
up front that ... their context is being actively compressed and only five
turns of reasoning are preserved."

Until now a mind's reasoning lived for one call: recall gave it what happened,
its `note` and notebook what it chose to write down, and nothing what it had
been working out. Here the thinking a mind did on a beat is kept in its own
state (`thoughts`: turn, the key of that turn's memory, the text), the last
`thoughts_kept()` turns of it, and handed back beside the memory of the turn
it was had in, oldest first -- `what_you_were_thinking` on that turn's row in
`memory.recent_memories`, which is the recent past in order.

A mind's own channel and nothing else's: the trace is this mind's, from its
own calls (`agents/character.py`), stored in its own state, delivered to its
own packet. No other mind, the Director or the page ever reads it, as no other
reader ever read `last_reasoning`.

OFF unless the `character_thoughts_kept` setting names a number of turns: a
packet grows by up to `THOUGHT_CHARS` a kept turn, and the owner decides once
the replay has measured what that buys and costs.
"""

from __future__ import annotations

from core.db import get_setting, q

#: Characters of one turn's thinking kept: the END of it, where a trace
#: concludes. A GLM 5.3 trace runs ~1,600-7,000 characters a call (measured
#: 2026-10-05: 400-1,800 reasoning tokens); an interaction loop can make
#: several calls a beat. Mine, named to the owner, unruled.
THOUGHT_CHARS = 6000


def thoughts_kept() -> int:
    """How many turns of its thinking a mind keeps: the `character_thoughts_kept`
    setting, 0 (off) when unset or unreadable."""
    try:
        return max(0, int(str(get_setting("character_thoughts_kept") or "0").strip() or 0))
    except (TypeError, ValueError):
        return 0


def keep_thought(state, turn_idx, key, texts, kept=None):
    """Store this beat's thinking in a mind's `state` (in place): `texts` are
    the beat's calls in order, joined, cut to its last `THOUGHT_CHARS`. A
    thought lives `kept` turns of the STORY, not of the mind's own beats: one
    had `kept` turns ago or longer is gone, however long the mind was quiet
    since. With the setting off nothing is kept, and what was kept goes -- a
    mind is never shown thinking the card says it does not have."""
    kept = thoughts_kept() if kept is None else int(kept)
    if kept <= 0:
        state.pop("thoughts", None)
        return state
    text = "\n\n".join(str(t).strip() for t in texts or () if str(t or "").strip())
    old = [t for t in state.get("thoughts") or []
           if isinstance(t, dict) and t.get("turn") != turn_idx
           and int(t.get("turn", -1)) > int(turn_idx) - kept]
    if text:
        old.append({"turn": int(turn_idx), "key": str(key or ""),
                    "thought": text if len(text) <= THOUGHT_CHARS else text[-THOUGHT_CHARS:]})
    if old:
        state["thoughts"] = old[-kept:]
    else:
        state.pop("thoughts", None)
    return state


def recent_thoughts(state, current_turn_idx, kept=None):
    """The thinking this mind kept from the last `kept` turns of the story
    before `current_turn_idx`, oldest first."""
    kept = thoughts_kept() if kept is None else int(kept)
    if kept <= 0:
        return []
    out = [t for t in (state or {}).get("thoughts") or []
           if isinstance(t, dict) and str(t.get("thought") or "").strip()
           and int(current_turn_idx) - kept <= int(t.get("turn", -1)) < int(current_turn_idx)]
    out.sort(key=lambda t: int(t["turn"]))
    return out[-kept:]


def beside_their_turns(chat_id, char_id, rows, thoughts, clock=None):
    """`rows` (the recent memories, oldest first) with each kept thought
    beside the memory of the turn it was had in, as `what_you_were_thinking`.
    A thought whose turn left no row in front of the mind stands at its
    turn's place on its own, with the turn's `when`."""
    if not thoughts:
        return list(rows or [])
    by_key = {str(t.get("key") or ""): t for t in thoughts if t.get("key")}
    out, placed = [], set()
    for row in rows or []:
        hit = by_key.get(str((row or {}).get("memory_ref") or ""))
        if hit is not None and hit["turn"] not in placed:
            row = dict(row, what_you_were_thinking=hit["thought"])
            placed.add(hit["turn"])
        out.append(row)
    loose = [t for t in thoughts if t["turn"] not in placed]
    if not loose:
        return out
    keys = [str((r or {}).get("memory_ref") or "") for r in out]
    turn_of = {}
    wanted = [k for k in keys if k]
    if wanted:
        for r in q("SELECT event_key, turn_idx FROM memories WHERE chat_id=? AND char_id=? "
                   "AND event_key IN (%s)" % ",".join("?" * len(wanted)), (chat_id, char_id, *wanted)):
            turn_of[r["event_key"]] = r["turn_idx"]
    for t in loose:
        stub = {"what_you_were_thinking": t["thought"]}
        if clock is not None:
            try:
                stub = {"when": clock.of_memory({"turn_idx": t["turn"]}), **stub}
            except Exception:  # noqa: BLE001 -- a thought needs no date to be had
                pass
        at = len(out)
        for i in range(len(out) - 1, -1, -1):
            turn = turn_of.get(keys[i]) if i < len(keys) else None
            if turn is not None and turn <= t["turn"]:
                at = i + 1
                break
            if turn is not None:
                at = i
        out.insert(at, stub)
        # The stub carries its own turn, so a later loose thought between the
        # same two rows lands after it, not before.
        marker = "\x00thought:%d" % int(t["turn"])
        keys.insert(at, marker)
        turn_of[marker] = int(t["turn"])
    return out
