"""A Jev label set for tuning retrieval as a net, and the offline evaluator.

`label` mode, per beat: rebuild the beat's retrieval inputs (the character's
perception view as the query; goal, mood and concerns from its own result on
the turn before), compute every candidate generator's ranking and today's
fused ranking, have Jev grade the WHOLE visible bank (`situation`, `useful`,
graded), and run Jev feedback (grade a small first net, then pull the nearest
neighbours of its top picks) -- all cached as ids and grades so that any net
can then be scored offline without calling Jev again.

`score` mode: recall@N of the reference (each beat's top `--reference` by the
larger grade) for a set of net configurations, over the cached beats.
`feedback` mode: recompute Jev-feedback nets for other splits, no Jev calls.
`channels` mode: grade the packet's other channels over each cached bank.
`fit` mode: learning to rank -- weighted RRF over every lane, fitted to a
reference by coordinate ascent, leave-one-beat-out, then replayed with the
previous beat's packet as a realistic primed lane.

Usage:
    ENGINE_DB=<a copy> python tools/jev_net_labels.py label --chat 63 --char 35 \\
        --turns 1847,1851,... --out labels_63.json
    python tools/jev_net_labels.py score --labels labels_63.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

FEEDBACK_FIRST = 40
FEEDBACK_SEEDS = 5
FEEDBACK_TOTAL = 80


def state_entering(chat_id, char_id, turn_idx):
    """Goal, mood and concerns the character carried INTO this beat: its own
    result on the previous turn (first round naming it), else nothing."""
    from core.db import q

    prev = q("SELECT id FROM turns WHERE chat_id=? AND idx=?", (chat_id, turn_idx - 1), one=True)
    if not prev:
        return {}
    row = q("SELECT v.content FROM steps s JOIN variants v ON v.step_id=s.id "
            "WHERE s.turn_id=? AND s.key='interaction_loop' AND v.active=1",
            (prev["id"],), one=True)
    if not row:
        return {}
    for rnd in json.loads(row["content"]).get("rounds") or []:
        result = rnd.get("result") or {}
        if str(result.get("char_id") or "") == str(char_id) and result.get("active_state"):
            return result["active_state"]
    return {}


def label_beat(chat_id, char_id, turn_id):
    import numpy as np

    import jev_memory_probe as probe
    import jev_net_recall as recall
    from core.db import q
    from mind.memory_common import _cos, _vec

    turn = q("SELECT idx FROM turns WHERE id=?", (turn_id,), one=True)
    inputs = recall.beat(chat_id, char_id, turn_id)
    active = state_entering(chat_id, char_id, turn["idx"])
    if active:
        concerns = active.get("active_concerns") or []
        inputs.update(goal=str(active.get("goal") or ""), mood=str(active.get("mood") or ""),
                      concerns=" ".join(str(c.get("text") if isinstance(c, dict) else c)
                                        for c in concerns))
    aspects = [(label, text) for label, text in (
        ("what you are trying to do", inputs["goal"]),
        ("how you are feeling", inputs["mood"]),
        ("what is still unsettled", inputs["concerns"])) if str(text or "").strip()]
    memories, ranks = recall.generators(inputs, aspects)
    fused = [row["id"] for row in probe.net(dict(inputs), inputs["view"], len(memories), aspects)]

    state = probe.state_for(inputs)
    questions = {}
    for mid, mem in memories.items():
        body = "\n\n" + probe.memory_text(mem, inputs["turn_idx"])
        for channel in ("situation", "useful"):
            questions[f"{channel}__{mid}"] = {
                "type": "choice", "instructions": probe.GRADED_CHANNELS[channel] + body,
                "criteria": {key: label for key, (label, _w) in probe.SCALE.items()}}
    grades, seconds, _raw = probe.ask_jev(state, questions)
    judged = {mid: max(grades.get(f"situation__{mid}") or 0.0,
                       grades.get(f"useful__{mid}") or 0.0) for mid in memories}

    # Jev feedback: grade a small first net, then pull the nearest neighbours
    # (cue or content vector) of its top picks until the net holds TOTAL rows.
    rows = {r["id"]: r for r in q("SELECT id, embedding, cue_embedding FROM memories "
                                  "WHERE chat_id=? AND char_id=?", (chat_id, char_id))}
    vec = {mid: (_vec(rows[mid]["embedding"]), _vec(rows[mid]["cue_embedding"]))
           for mid in memories if mid in rows}
    feedback = {}
    for first_name, first_order in (("fused", fused), ("union", recall.union_net(ranks, len(memories)))):
        first = first_order[:FEEDBACK_FIRST]
        seeds = sorted(first, key=lambda mid: -judged[mid])[:FEEDBACK_SEEDS]

        def near(mid):
            best = 0.0
            for seed in seeds:
                for a in (vec.get(mid) or (None, None)):
                    for b in (vec.get(seed) or (None, None)):
                        if a is not None and b is not None:
                            best = max(best, float(_cos(a, b)))
            return best
        taken = set(first)
        extra = [mid for mid in sorted(memories, key=lambda mid: -near(mid)) if mid not in taken]
        feedback[first_name] = first + extra[:FEEDBACK_TOTAL - len(first)]
    del np
    return {"turn_id": turn_id, "turn_idx": inputs["turn_idx"], "bank": len(memories),
            "jev_questions": len(questions), "jev_seconds": seconds,
            "mood": inputs["mood"][:120], "goal": inputs["goal"][:120],
            "judged": {str(mid): round(v, 4) for mid, v in judged.items()},
            "ranks": ranks, "fused": fused, "feedback": feedback}


def label(args):
    out = Path(args.out)
    data = json.loads(out.read_text()) if out.exists() else {"chat": args.chat, "char": args.char, "beats": []}
    done = {b["turn_id"] for b in data["beats"]}
    for turn_id in [int(t) for t in args.turns.split(",") if t.strip()]:
        if turn_id in done:
            continue
        beat = label_beat(args.chat, args.char, turn_id)
        data["beats"].append(beat)
        out.write_text(json.dumps(data), encoding="utf-8")
        print(f"turn {turn_id} idx {beat['turn_idx']}: bank {beat['bank']}, "
              f"{beat['jev_questions']} q in {beat['jev_seconds']}s")


def channels(args):
    """Grade the packet's other channels (`senses`, `mood_match`,
    `mood_contrast` by default) over every cached beat's whole bank, stored
    per channel beside `judged` -- so a net can be scored against every
    channel a packer would draw from, not only the topical two."""
    import jev_memory_probe as probe
    import jev_net_recall as recall
    from core.db import q
    from mind.memory_read import visible_memory_rows
    from mind.memory_write import _row_memory

    path = Path(args.labels)
    data = json.loads(path.read_text())
    wanted = [c for c in args.channels.split(",") if c.strip()]
    for beat in data["beats"]:
        have = beat.setdefault("by_channel", {})
        todo = [c for c in wanted if c not in have]
        if not todo:
            continue
        inputs = recall.beat(data["chat"], data["char"], beat["turn_id"])
        idx = q("SELECT idx FROM turns WHERE id=?", (beat["turn_id"],), one=True)["idx"]
        active = state_entering(data["chat"], data["char"], idx)
        if active:
            concerns = active.get("active_concerns") or []
            inputs.update(goal=str(active.get("goal") or ""), mood=str(active.get("mood") or ""),
                          concerns=" ".join(str(c.get("text") if isinstance(c, dict) else c) for c in concerns))
        rows = visible_memory_rows(data["chat"], data["char"], before_turn_idx=inputs["turn_idx"],
                                   viewer_frame_id=None, include_archived=True)
        memories = {m["id"]: m for m in (_row_memory(r) for r in rows)}
        questions = {}
        for mid, mem in memories.items():
            body = "\n\n" + probe.memory_text(mem, inputs["turn_idx"])
            for channel in todo:
                questions[f"{channel}__{mid}"] = {
                    "type": "choice", "instructions": probe.GRADED_CHANNELS[channel] + body,
                    "criteria": {key: label for key, (label, _w) in probe.SCALE.items()}}
        grades, seconds, _raw = probe.ask_jev(probe.state_for(inputs), questions)
        for channel in todo:
            have[channel] = {str(mid): round(grades[f"{channel}__{mid}"], 4) for mid in memories
                             if grades.get(f"{channel}__{mid}") is not None}
        path.write_text(json.dumps(data), encoding="utf-8")
        print(f"turn {beat['turn_id']}: {len(questions)} questions in {seconds}s")


def feedback_nets(args):
    """Recompute Jev-feedback nets for other (first, total) splits from the
    cached labels and the stored vectors -- no Jev calls. A split's first
    part is the top of today's fused ranking or the union; its seeds are the
    first part's best by Jev's cached grade; the rest are the nearest
    neighbours of those seeds."""
    import jev_net_recall as recall
    from core.db import q
    from mind.memory_common import _cos, _vec

    path = Path(args.labels)
    data = json.loads(path.read_text())
    rows = {r["id"]: r for r in q("SELECT id, embedding, cue_embedding FROM memories "
                                  "WHERE chat_id=? AND char_id=?", (data["chat"], data["char"]))}
    vec = {mid: (_vec(r["embedding"]), _vec(r["cue_embedding"])) for mid, r in rows.items()}
    splits = [tuple(int(x) for x in s.split("+")) for s in args.splits.split(",")]
    for beat in data["beats"]:
        judged = {int(k): v for k, v in beat["judged"].items()}
        ranks = {name: [int(m) for m in r] for name, r in beat["ranks"].items()}
        firsts = {"fused": [int(m) for m in beat["fused"]],
                  "union": recall.union_net(ranks, len(judged))}
        for first_name, order in firsts.items():
            for first_n, rest_n in splits:
                first = order[:first_n]
                seeds = sorted(first, key=lambda mid: -judged[mid])[:args.seeds]
                seed_vecs = [v for s in seeds for v in vec.get(s, (None, None)) if v is not None]

                def near(mid):
                    own = [v for v in vec.get(mid, (None, None)) if v is not None]
                    return max((float(_cos(a, b)) for a in own for b in seed_vecs), default=0.0)
                taken = set(first)
                extra = [mid for mid in sorted(judged, key=lambda mid: -near(mid)) if mid not in taken]
                beat["feedback"][f"{first_name} {first_n}+{rest_n}"] = first + extra[:rest_n]
    path.write_text(json.dumps(data), encoding="utf-8")
    print(f"recomputed feedback nets {args.splits} for {len(data['beats'])} beats")


def evaluate(args):
    import jev_net_recall as recall

    data = json.loads(Path(args.labels).read_text())
    beats = sorted(data["beats"], key=lambda b: b["turn_idx"])
    at = (25, 50, 80, 100, 150, 200)
    table = {}
    previous_top = None
    for beat in beats:
        judged = {int(k): v for k, v in beat["judged"].items()}
        reference = sorted(judged, key=lambda mid: -judged[mid])[:args.reference]
        ranks = {name: [int(m) for m in r] for name, r in beat["ranks"].items()}
        nets = {
            "fused (today)": [int(m) for m in beat["fused"]],
            "union (all generators)": recall.union_net(ranks, len(judged)),
            "fused + recency": recall.union_net({"fused": [int(m) for m in beat["fused"]],
                                                 "recency": ranks["recency"]}, len(judged)),
        }
        if previous_top:
            primed = [m for m in previous_top if m in judged]
            nets["union + primed"] = recall.union_net({"primed": primed, **ranks}, len(judged))
            nets["fused + recency + primed"] = recall.union_net(
                {"primed": primed, "fused": [int(m) for m in beat["fused"]],
                 "recency": ranks["recency"]}, len(judged))
        for name, order in beat["feedback"].items():
            label_ = (f"feedback from {name}@{FEEDBACK_FIRST} -> {FEEDBACK_TOTAL}"
                      if name in ("fused", "union") else f"feedback {name}")
            nets[label_] = [int(m) for m in order]
        for name, order in nets.items():
            for n in at:
                if n > len(order) and not name.startswith("feedback"):
                    continue
                hit = sum(1 for mid in reference if mid in set(order[:n])) / len(reference)
                table.setdefault(name, {}).setdefault(n, []).append(hit)
        previous_top = sorted(judged, key=lambda mid: -judged[mid])[:args.reference]
    print(f"{len(beats)} beats, reference = top {args.reference} by Jev's larger grade")
    for name, row in table.items():
        cells = "  ".join(f"@{n}: {sum(v)/len(v):.0%}" for n, v in sorted(row.items()))
        print(f"  {name:38} {cells}")


#: Lanes a fitted net may weight: every cached generator, today's fused
#: ranking, and five built here from the labels and the rows themselves.
FIT_BASE = ["fused", "semantic", "cue", "keyword", "recency", "importance",
            "aspect:what you are trying to do", "aspect:how you are feeling",
            "aspect:what is still unsettled",
            # written by tools/jev_moment_affect.py when it has been run
            "moment_contrast", "moment_match", "mood_opposite", "mood_same"]
FIT_LANES = FIT_BASE + ["primed", "primed_nb", "here", "valence_match", "valence_contrast"]
FIT_GRID = (0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0)
FIT_KS = (5, 15, 30, 60)
PACKET_CHANNELS = ("senses", "mood_match", "mood_contrast")
#: The owner's "fun" sections (2026-09-26) and the tact channel beside them;
#: a packet section of each would hold a few rows, so the reference is 3.
FUN_CHANNELS = ("callback", "sore", "irony", "tease")


def _fit_beats(data):
    """Per beat: ids, the rank matrix over FIT_LANES (primed columns empty
    until `_set_primed`), content vectors, grades and the references."""
    import numpy as np

    from core.db import q
    from mind.memory_common import _vec

    mem = {r["id"]: r for r in q("SELECT id, turn_idx, location, embedding, encoding_valence FROM memories "
                                 "WHERE chat_id=? AND char_id=?", (data["chat"], data["char"]))}
    out = []
    for beat in sorted(data["beats"], key=lambda b: b["turn_idx"]):
        judged = {int(k): float(v) for k, v in beat["judged"].items()}
        mids = sorted(judged)
        index = {m: i for i, m in enumerate(mids)}
        R = np.full((len(mids), len(FIT_LANES)), 1e9)
        ranks = {name: [int(m) for m in r] for name, r in beat["ranks"].items()}
        ranks["fused"] = [int(m) for m in beat["fused"]]
        for j, name in enumerate(FIT_BASE):
            for pos, m in enumerate(ranks.get(name) or [], 1):
                if m in index:
                    R[index[m], j] = pos
        # here: rows at the location of the character's latest memory, newest first
        latest = max(mids, key=lambda m: (mem[m]["turn_idx"] or -1, m))
        loc = (mem[latest]["location"] or "").strip()
        here = sorted((m for m in mids if loc and (mem[m]["location"] or "").strip() == loc),
                      key=lambda m: -(mem[m]["turn_idx"] or -1))
        for pos, m in enumerate(here, 1):
            R[index[m], FIT_LANES.index("here")] = pos
        # valence: encoded feeling nearest / farthest from the surface affect entering the beat
        active = state_entering(data["chat"], data["char"], beat["turn_idx"])
        now = (((active or {}).get("affect") or {}).get("surface") or {}).get("valence")
        if now is not None:
            ev = np.array([mem[m]["encoding_valence"] if mem[m]["encoding_valence"] is not None else np.nan
                           for m in mids])
            dist = np.abs(ev - float(now))
            ok = ~np.isnan(dist)
            for name, key in (("valence_match", dist), ("valence_contrast", -dist)):
                order = [i for i in np.argsort(np.where(ok, key, np.inf)) if ok[i]]
                R[order, FIT_LANES.index(name)] = np.arange(1, len(order) + 1)
        dim = len(next(v for v in (_vec(r["embedding"]) for r in mem.values()) if v is not None))
        E = np.stack([_vec(mem[m]["embedding"]) if mem[m]["embedding"] else np.zeros(dim, dtype=np.float32)
                      for m in mids])
        g = np.array([judged[m] for m in mids])
        refs = {"topical top 30": np.argsort(-g)[:30]}
        packet = list(refs["topical top 30"][:12])
        orders = {}
        for ch, grades in (beat.get("by_channel") or {}).items():
            cg = {int(k): v for k, v in grades.items()}
            orders[ch] = np.argsort(-np.array([cg.get(m, 0.0) for m in mids]))
        for ch in PACKET_CHANNELS:
            if ch in orders:
                refs[f"{ch} top 10"] = orders[ch][:10]
                packet += [i for i in orders[ch][:6] if i not in packet]
        refs["packet"] = np.array(packet)
        if all(ch in orders for ch in FUN_CHANNELS):
            fun = list(packet)
            for ch in FUN_CHANNELS:
                refs[f"{ch} top 3"] = orders[ch][:3]
                fun += [i for i in orders[ch][:3] if i not in fun]
            refs["packet + fun"] = np.array(fun)
        out.append({"mids": mids, "index": index, "R": R, "E": E, "g": g, "refs": refs,
                    "ref": refs["topical top 30"], "turn_idx": beat["turn_idx"]})
    return out


def _set_primed(p, primed_ids):
    import numpy as np

    R = p["R"]
    R[:, FIT_LANES.index("primed")] = 1e9
    R[:, FIT_LANES.index("primed_nb")] = 1e9
    rows = [p["index"][m] for m in primed_ids if m in p["index"]]
    for pos, i in enumerate(rows, 1):
        R[i, FIT_LANES.index("primed")] = pos
    if rows:
        order = np.argsort(-(p["E"] @ p["E"][rows].T).max(axis=1))
        R[order, FIT_LANES.index("primed_nb")] = np.arange(1, len(order) + 1)


def _net_order(p, w, k):
    import numpy as np

    return np.argsort(-(w / (k + p["R"])).sum(axis=1))


def _fit_weights(ps, net_size):
    """Coordinate ascent on the lane weights, k from a grid: mean recall of
    each beat's `ref` inside the first `net_size` rows."""
    import numpy as np

    def objective(w, k):
        return float(np.mean([np.isin(p["ref"], _net_order(p, w, k)[:net_size]).mean() for p in ps]))

    best = (-1.0, None, None)
    for k in FIT_KS:
        w = np.ones(len(FIT_LANES))
        score = objective(w, k)
        for _sweep in range(6):
            changed = False
            for j in range(len(FIT_LANES)):
                for val in FIT_GRID:
                    if val != w[j]:
                        trial = w.copy()
                        trial[j] = val
                        s = objective(trial, k)
                        if s > score + 1e-9:
                            score, w, changed = s, trial, True
            if not changed:
                break
        if score > best[0]:
            best = (score, w, k)
    return best


def fit(args):
    """Learning to rank on the cached labels: weighted RRF over FIT_LANES,
    fitted by coordinate ascent to `--target`, scored leave-one-beat-out
    against every reference, then replayed with a REALISTIC primed lane --
    the previous beat's packet as Jev would have picked it from the previous
    NET, not from the whole bank."""
    import numpy as np

    data = json.loads(Path(args.labels).read_text())
    P = _fit_beats(data)
    for i, p in enumerate(P):
        _set_primed(p, [P[i - 1]["mids"][j] for j in P[i - 1]["refs"]["topical top 30"]] if i else [])
    usable = P[1:]
    for p in P:
        p["ref"] = p["refs"][args.target]
    n = args.net

    def show(label_, orders):
        cells = []
        for name in usable[0]["refs"]:
            rec = np.mean([np.isin(p["refs"][name], o[:n]).mean() for p, o in zip(usable, orders)])
            size = np.median([np.argsort(o)[p["refs"][name]].max() + 1 for p, o in zip(usable, orders)])
            cells.append(f"{name}: {rec:.0%} (all at {int(size)})")
        at = {m: np.mean([np.isin(p["ref"], o[:m]).mean() for p, o in zip(usable, orders)]) for m in (50, 100, 150, 200)}
        print(f"  {label_}\n      {args.target} @50/100/150/200: " + " / ".join(f"{v:.0%}" for v in at.values())
              + f"\n      @{n} per reference: " + " | ".join(cells))

    fused_only = np.zeros(len(FIT_LANES))
    fused_only[FIT_LANES.index("fused")] = 1
    show("today: fused", [_net_order(p, fused_only, 60) for p in usable])
    orders = []
    for i, held in enumerate(usable):
        _s, w, k = _fit_weights([p for j, p in enumerate(usable) if j != i], n)
        orders.append(_net_order(held, w, k))
    show(f"fitted to {args.target}, leave one beat out", orders)
    score, w, k = _fit_weights(usable, n)
    print(f"  weights fitted on all {len(usable)} beats (k={k}, in-sample {score:.0%}): " + ", ".join(
        f"{name.replace('aspect:', '')} {v}" for name, v in sorted(zip(FIT_LANES, w), key=lambda t: -t[1]) if v))
    packet, rows = [], []
    for i, p in enumerate(P):
        _set_primed(p, packet)
        order = _net_order(p, w, k)
        if i:
            rows.append(order)
        inside = order[:n]
        packet = [p["mids"][j] for j in inside[np.argsort(-p["g"][inside])][:30]]
    show("the same weights, REALISTIC primed (in-sample weights)", rows)
    Path(args.out).write_text(json.dumps({"target": args.target, "net": n, "k": k,
                                          "weights": dict(zip(FIT_LANES, map(float, w)))}, indent=1))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p_label = sub.add_parser("label")
    p_label.add_argument("--chat", type=int, required=True)
    p_label.add_argument("--char", type=int, required=True)
    p_label.add_argument("--turns", required=True, help="comma-separated turn ids")
    p_label.add_argument("--out", required=True)
    p_eval = sub.add_parser("score")
    p_eval.add_argument("--labels", required=True)
    p_eval.add_argument("--reference", type=int, default=30)
    p_feed = sub.add_parser("feedback")
    p_feed.add_argument("--labels", required=True)
    p_feed.add_argument("--splits", default="40+60,50+50,30+70")
    p_feed.add_argument("--seeds", type=int, default=FEEDBACK_SEEDS)
    p_chan = sub.add_parser("channels")
    p_chan.add_argument("--labels", required=True)
    p_chan.add_argument("--channels", default="senses,mood_match,mood_contrast")
    p_fit = sub.add_parser("fit")
    p_fit.add_argument("--labels", required=True)
    p_fit.add_argument("--target", default="topical top 30",
                       help="'topical top 30', 'packet', or '<channel> top 10'")
    p_fit.add_argument("--net", type=int, default=100)
    p_fit.add_argument("--out", required=True, help="where the fitted weights are written")
    args = parser.parse_args()
    {"label": label, "score": evaluate, "feedback": feedback_nets, "channels": channels,
     "fit": fit}[args.mode](args)


if __name__ == "__main__":
    main()
