#!/usr/bin/env python3
"""Surface-affect saturation: measure it corpus-wide, replay a fix offline.

THE DEFECT THIS INSTRUMENTS. `resolve_affect` decays an unreinforced mood
toward baseline and clamps the model's proposal at +/-1 -- decay handles
FADING, nothing handles SATURATION. A model that sees its own ceiling-pinned
surface in the payload proposes the ceiling again, so a surface that reaches
maximum stays there, and the most intense beat of the story lands with no
headroom -- mathematically flatter than its own build-up. Measured on chat
71 (Elyra, char 56): pinned ~0.55 above her own baseline from turn 13, and
her climax at turn 30 scored LOWER than the twelve-beat plateau before it.
Corpus sweep: 21 of 44 characters with >=8 beats carry a >=6-beat pinned
streak at >=0.9; three stories hold thirty-beat valence streaks.

Two commands, both READ-ONLY (mode=ro; this tool never writes a database):

    python tools/affect_replay.py sweep
    python tools/affect_replay.py replay --chat 71 --char 56

`sweep` prints per-(chat, character) saturation statistics over every stored
character result. `replay` re-resolves one character's whole stored beat
sequence through `affect.resolve_affect` twice -- habituation off (shipped)
and on -- and prints both trajectories beside the model's own proposals, so
a resolver change is judged on real story data with no model calls.

GROUND TRUTH AND APPROXIMATIONS. Per-turn checkpoints carry the state each
beat actually ENTERED live -- the committed surface and the resolved hedonic
charge -- so the replay prints the live committed trajectory beside both
arms and seeds `unresolved_drive` from the live charge (zeroed on a declared
release, exactly as commit does). What is still approximated, identically in
both arms: `priority_of` treats every intention id the beat's own
wants/goal_impacts cite as steering (priority 0.8), and beats are spaced by
turn-index deltas rather than `elapsed_psych_units` over the simulation
clock. The `off` arm therefore validates the instrument -- it should track
the live column closely -- and the `on` arm is the same inputs through the
habituating resolver.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _connect(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _character_beats(con, chat_id=None):
    """(chat_id, char_key) -> [beat, ...] oldest first, one per turn."""
    con.row_factory = sqlite3.Row
    where = "AND t.chat_id=?" if chat_id is not None else ""
    args = (chat_id,) if chat_id is not None else ()
    rows = con.execute(f"""
        SELECT t.chat_id, t.idx, v.content FROM variants v
        JOIN steps s ON s.id=v.step_id JOIN turns t ON t.id=s.turn_id
        WHERE s.key IN ('interaction_loop','reaction_loop') AND v.active=1
        {where} ORDER BY t.chat_id, t.idx""", args)
    beats = collections.defaultdict(list)
    for r in rows:
        try:
            content = json.loads(r["content"])
        except (TypeError, ValueError):
            continue
        results = (content.get("character_results")
                   or content.get("reaction_results") or {})
        if not isinstance(results, dict):
            continue
        for who, res in results.items():
            if isinstance(res, dict):
                beats[(r["chat_id"], str(who))].append(
                    {"idx": r["idx"], "result": res})
    return beats


def _surface(res):
    asv = res.get("active_state") or {}
    aff = asv.get("affect")
    aff = aff if isinstance(aff, dict) else {}
    surf = aff.get("surface")
    surf = surf if isinstance(surf, dict) else aff
    try:
        return float(surf.get("valence")), float(surf.get("arousal"))
    except (TypeError, ValueError):
        return None


def cmd_sweep(args):
    con = _connect(args.db)
    beats = _character_beats(con)

    def streak(values, threshold):
        best = current = 0
        for value in values:
            current = current + 1 if value >= threshold else 0
            best = max(best, current)
        return best

    rows = []
    for (cid, who), items in beats.items():
        pts = [p for p in (_surface(b["result"]) for b in items) if p]
        if len(pts) < args.min_beats:
            continue
        vs = [p[0] for p in pts]
        ars = [p[1] for p in pts]
        rows.append((
            cid, who, len(pts),
            100.0 * sum(1 for x in vs if x >= 0.9) / len(pts),
            100.0 * sum(1 for x in ars if x >= 0.9) / len(pts),
            streak(vs, 0.9), streak(ars, 0.9),
        ))
    rows.sort(key=lambda r: -max(r[5], r[6]))
    print(f"{'chat':>5} {'char':>5} {'beats':>6} {'%v>=.9':>7} "
          f"{'%a>=.9':>7} {'vstreak':>8} {'astreak':>8}")
    for row in rows:
        print("%5d %5s %6d %7.0f %7.0f %8d %8d" % row)
    pinned = sum(1 for r in rows if max(r[5], r[6]) >= 6)
    print(f"\n{len(rows)} characters with >={args.min_beats} beats; "
          f"{pinned} carry a >=6-beat pinned streak (>=0.9) on an axis.")


def _replay_priority(result):
    """Every serves key this beat cites reads as an established intention."""
    from mind import affect

    cited = set()
    asv = result.get("active_state") or {}
    for want in (asv.get("wants") or []):
        if isinstance(want, dict) and want.get("serves"):
            cited.add(str(want["serves"]))
    for gi in ((result.get("appraisal") or {}).get("goal_impacts") or []):
        if isinstance(gi, dict) and gi.get("serves"):
            cited.add(str(gi["serves"]))
    cited -= {"drive", "situational"}
    return lambda serves: affect.serves_priority(serves, cited)


def _checkpoint_states(con, chat_id, char_id):
    """turn_idx -> the state that turn ENTERED live: {surface, charge}.

    A checkpoint at idx N snapshots durable state before turn N runs, i.e.
    what turn N-1 committed -- the ground truth this replay is judged
    against."""
    con.row_factory = sqlite3.Row
    states = {}
    for row in con.execute(
            "SELECT turn_idx, blob FROM checkpoints WHERE chat_id=? "
            "ORDER BY turn_idx", (chat_id,)):
        try:
            blob = json.loads(row["blob"])
        except (TypeError, ValueError):
            continue
        chars = blob.get("chars") or {}
        entry = chars.get(str(char_id)) if isinstance(chars, dict) else None
        state = (entry or {}).get("state")
        if isinstance(state, str):
            try:
                state = json.loads(state)
            except (TypeError, ValueError):
                state = {}
        asv = (state or {}).get("active_state") or {}
        affect_blob = asv.get("affect") or {}
        states[row["turn_idx"]] = {
            "surface": (affect_blob.get("surface")
                        if isinstance(affect_blob.get("surface"), dict)
                        else None),
            "baseline": (affect_blob.get("baseline")
                         if isinstance(affect_blob.get("baseline"), dict)
                         else None),
            "charge": (asv.get("hedonic") or {}).get("charge"),
        }
    return states


def cmd_replay(args):
    from mind import affect

    con = _connect(args.db)
    beats = _character_beats(con, chat_id=args.chat).get(
        (args.chat, str(args.char)), [])
    if not beats:
        print(f"no stored character results for chat {args.chat} "
              f"char {args.char}")
        return
    live = _checkpoint_states(con, args.chat, args.char)

    # The character's own resting point: the earliest checkpoint that
    # carries one, falling back to the live committed state.
    baseline = next((s["baseline"] for _, s in sorted(live.items())
                     if s.get("baseline")), None)
    if baseline is None:
        row = con.execute(
            "SELECT cc.state FROM chat_chars cc WHERE cc.chat_id=? AND "
            "cc.char_id=?", (args.chat, args.char)).fetchone()
        state = json.loads(row["state"] or "{}") if row else {}
        baseline = (((state.get("active_state") or {}).get("affect") or {})
                    .get("baseline")) or {"valence": 0.0, "arousal": 0.3}
    print(f"baseline: valence={baseline.get('valence')} "
          f"arousal={baseline.get('arousal')}\n")

    arms = {"off": {"prev": None}, "on": {"prev": None}}
    prev_idx = None
    header = (f"{'idx':>4} {'rel':>3} | {'live_v':>6} {'live_a':>6} | "
              f"{'off_v':>6} {'off_a':>6} | {'on_v':>6} {'on_a':>6} | "
              f"{'s_v':>5} {'s_a':>5}")
    print(header)
    print("-" * len(header))
    last_idx = beats[-1]["idx"]
    for beat in beats:
        res = beat["result"]
        asv = res.get("active_state") or {}
        appraisal_input = res.get("appraisal") or {}
        released = bool((asv.get("hedonic") or {}).get("released"))
        turns = max(1, beat["idx"] - prev_idx) if prev_idx is not None else 1
        prev_idx = beat["idx"]
        # The charge this beat ENTERED with, from the live resolved chain.
        entering = live.get(beat["idx"]) or {}
        try:
            charge = float(entering.get("charge") or 0.0)
        except (TypeError, ValueError):
            charge = 0.0
        unresolved = 0.0 if released else charge
        appraisal_out = affect.appraise(
            appraisal_input.get("goal_impacts") or [],
            _replay_priority(res),
            dimensions=appraisal_input,
            unresolved_drive=unresolved,
        )
        proposed = asv.get("affect") or asv.get("mood")
        for arm, habituate in (("off", False), ("on", True)):
            arms[arm]["prev"] = affect.resolve_affect(
                arms[arm]["prev"], appraisal_out, baseline, turns,
                proposed, habituate=habituate, released=released)
        # What this beat actually committed live = the state the NEXT
        # checkpoint carries. The final beat has no successor checkpoint.
        after = (live.get(beat["idx"] + 1) or {}).get("surface") \
            if beat["idx"] < last_idx or (beat["idx"] + 1) in live else None
        live_v = (after or {}).get("valence")
        live_a = (after or {}).get("arousal")
        off = arms["off"]["prev"]["surface"]
        on = arms["on"]["prev"]["surface"]
        hab = arms["on"]["prev"].get("habituation") or {}
        print("%4d %3s | %6s %6s | %6.2f %6.2f | %6.2f %6.2f |"
              " %5.2f %5.2f" % (
                  beat["idx"], "REL" if released else "",
                  ("%6.2f" % live_v) if live_v is not None else "  --",
                  ("%6.2f" % live_a) if live_a is not None else "  --",
                  off["valence"], off["arousal"],
                  on["valence"], on["arousal"],
                  hab.get("valence", 0.0), hab.get("arousal", 0.0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="engine.db")
    sub = ap.add_subparsers(dest="command", required=True)
    sweep = sub.add_parser("sweep")
    sweep.add_argument("--min-beats", type=int, default=8)
    sweep.set_defaults(fn=cmd_sweep)
    replay = sub.add_parser("replay")
    replay.add_argument("--chat", type=int, required=True)
    replay.add_argument("--char", type=int, required=True)
    replay.set_defaults(fn=cmd_replay)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
