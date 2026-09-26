"""Is recall more relevant after a Jev-filtered net than after today's RRF?

An experiment instrument for `docs/design/DESIGN_JEV_CHARACTER_PASS.md`
(2026-09-26). The owner: "how would you grade how relevant the recall is now
compared to what it was with the @100 filter vs the pure @24 rrf?" -- and "79%
doesn't mean it's bad it may actually be a massive improvement." A net that
keeps 79% of Jev's picks says nothing yet about whether what the character
RECEIVES is better than today, so this grades the packets themselves, blind,
by judges that are not Jev.

`build`, per labelled beat with a previous beat (`jev_net_labels.py` cache),
four packets of 24 rows, each excluding the recent buffer the character is
handed separately (the last 4 turns, up to 12 rows), as production does:

- `old`: production recall as shipped -- `search_memories(view, k=24)` with
  the production aspects (goal, mood, and live concerns interleaved with the
  summary's unresolved threads, at most 6), diversity pass on;
- `new`: the fitted net of 100 (weights fitted WITHOUT this beat, primed by
  the previous beat's packet as picked from the previous beat's own net), then
  Jev's top 24 by the larger of its `situation` and `useful` grades;
- `new_dedup`: the same, skipping a row within cosine 0.90 of one already
  taken (one belief reworded) and refilling from the net;
- `ideal`: Jev's top 24 over the whole bank -- the judge reading everything.

It writes the packets (with the key) and, separately, one blind SHEET per
beat: the character's situation and the union of the four packets shuffled
under opaque ids, so a grader cannot tell which system chose a row.

`judge`: the `utility` model grades every sheet, 0-3 per row.
`score`: per packet -- mean grade, share graded 2+ and 0, near-duplicate pairs
-- under any grades file (the `utility` judge's, or another grader's written in
the same shape: `{beat: {opaque_id: grade}}`).

`build --size 48` builds the same four packets at 48 rows, for the question
the owner's offloading theory turns on: does the knee at k=24
(`RETRIEVAL_COST.md` section 6, traced there to irrelevant rows past 24) hold
for a packet a judge chose?

Usage:
    ENGINE_DB=<a copy> python tools/jev_packet_compare.py build --labels labels_63.json --out cmp_63
    ENGINE_DB=<a copy> python tools/jev_packet_compare.py judge --dir cmp_63
    python tools/jev_packet_compare.py score --dir cmp_63 --grades cmp_63/grades_utility.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PACKET = 24
NET = 100
NEAR = 0.90
PACKETS = ("old", "new", "new_dedup", "ideal")

JUDGE_SYSTEM = """You grade how useful it would be for a character to have each of their own memories in mind right now.

You get the character's situation -- what they perceive, how they feel, what they are trying to do, what is unsettled for them -- and a list of their memories in random order. Grade every memory on its own:
0 = it has nothing to do with this moment;
1 = loosely related background; having it in mind would not change anything;
2 = relevant: it bears on what is happening now or on what they are trying to do;
3 = essential: they would be poorer, right now, for not remembering it.

Any number of memories may deserve any grade. Return JSON only: {"grades": {"M1": 0, "M2": 3, ...}} with every id."""


def _production_aspects(chat_id, char_id, turn_idx, active):
    """The aspects `build_character_memory_context` passes, built its way."""
    from itertools import zip_longest

    from mind.memory import get_memory_summary

    summary = get_memory_summary(chat_id, char_id, before_turn_idx=turn_idx)
    live = [str(item) for item in (active.get("active_concerns") or []) if str(item).strip()]
    threads = [str(item) for item in (summary.get("unresolved_threads") or []) if str(item).strip()]
    unresolved = list(dict.fromkeys(item for pair in zip_longest(live, threads)
                                    for item in pair if item is not None))[:6]
    return [("what you are trying to do", str(active.get("goal") or "")),
            ("how you are feeling", str(active.get("mood") or "")),
            ("what is still unsettled", " ".join(unresolved))], unresolved


def build(args):
    import numpy as np

    import jev_memory_probe as probe
    import jev_net_labels as labels
    import jev_net_recall as recall
    from mind.memory import recent_memory_buffer, search_memories
    from mind.memory_read import visible_memory_rows
    from mind.memory_write import _row_memory

    data = json.loads(Path(args.labels).read_text())
    chat_id, char_id = data["chat"], data["char"]
    size = args.size
    P = labels._fit_beats(data)
    beats = sorted(data["beats"], key=lambda b: b["turn_idx"])
    for i, p in enumerate(P):  # training uses the ideal primed lane, as `fit` does
        labels._set_primed(p, [P[i - 1]["mids"][j] for j in P[i - 1]["refs"]["topical top 30"]] if i else [])
    usable = P[1:]
    lobo = {}
    for i, held in enumerate(usable):
        _s, w, k = labels._fit_weights([p for j, p in enumerate(usable) if j != i], NET)
        lobo[held["turn_idx"]] = (w, k)
    _s, w_all, k_all = labels._fit_weights(usable, NET)  # only to prime the first beat

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    packets, sheets = {}, {}
    prev_packet = []
    for p, beat in zip(P, beats):
        labels._set_primed(p, prev_packet)
        w, k = lobo.get(p["turn_idx"], (w_all, k_all))
        net = labels._net_order(p, w, k)[:NET]
        prev_packet = [p["mids"][j] for j in net[np.argsort(-p["g"][net])][:30]]
        if p["turn_idx"] not in lobo:
            continue
        idx = p["turn_idx"]
        active = labels.state_entering(chat_id, char_id, idx)
        inputs = recall.beat(chat_id, char_id, beat["turn_id"])
        recent = {m["id"] for m in recent_memory_buffer(chat_id, char_id, idx, turns=4, limit=12)}
        aspects, unresolved = _production_aspects(chat_id, char_id, idx, active or {})
        shipped = search_memories(chat_id, char_id, inputs["view"], k=size, include_archived=True,
                                  current_turn_idx=idx, chronological=True, aspects=aspects,
                                  record_access=False)
        old = [m["id"] for m in shipped if m["id"] not in recent][:size]
        grade = dict(zip(p["mids"], p["g"]))
        by_grade = [p["mids"][j] for j in net[np.argsort(-p["g"][net])] if p["mids"][j] not in recent]
        new = by_grade[:size]
        E = {m: p["E"][p["index"][m]] for m in p["mids"]}
        dedup = []
        for m in by_grade:
            if all(float(E[m] @ E[kept]) < NEAR for kept in dedup):
                dedup.append(m)
            if len(dedup) == size:
                break
        ideal = [m for m in sorted(p["mids"], key=lambda m: -grade[m]) if m not in recent][:size]
        packets[str(idx)] = {"turn_id": beat["turn_id"], "old": old, "new": new, "new_dedup": dedup,
                             "ideal": ideal, "recent": sorted(recent)}

        rows = {m["id"]: m for m in (_row_memory(r) for r in visible_memory_rows(
            chat_id, char_id, before_turn_idx=idx, viewer_frame_id=None, include_archived=True))}
        union = sorted({m for name in PACKETS for m in packets[str(idx)][name]})
        random.Random(f"{chat_id}:{idx}").shuffle(union)
        key = {f"M{n}": mid for n, mid in enumerate(union, 1)}
        packets[str(idx)]["key"] = key
        situation = "\n\n".join(part for part in (
            f"CHARACTER: {inputs['name']}",
            "WHAT THEY PERCEIVE RIGHT NOW:\n" + inputs["view"][:3000],
            "HOW THEY FEEL: " + str((active or {}).get("mood") or "unremarkable"),
            "WHAT THEY ARE TRYING TO DO: " + str((active or {}).get("goal") or "nothing in particular"),
            ("WHAT IS UNSETTLED FOR THEM: " + " | ".join(unresolved)) if unresolved else "") if part)
        sheets[str(idx)] = {"situation": situation,
                            "memories": [{"id": oid, "text": probe.memory_text(rows[mid], idx)}
                                         for oid, mid in key.items()]}
        print(f"beat {idx}: old {len(old)}, new {len(new)}, dedup {len(dedup)}, ideal {len(ideal)}, "
              f"sheet {len(union)} rows")
    (out / "packets.json").write_text(json.dumps(packets, indent=1), encoding="utf-8")
    (out / "sheets.json").write_text(json.dumps(sheets, indent=1), encoding="utf-8")


def judge(args):
    from agents.common import jparse
    from llm.providers import chat_complete

    folder = Path(args.dir)
    sheets = json.loads((folder / "sheets.json").read_text())
    path = folder / "grades_utility.json"
    grades = json.loads(path.read_text()) if path.exists() else {}
    for beat, sheet in sheets.items():
        if beat in grades and len(grades[beat]) == len(sheet["memories"]):
            continue
        user = (sheet["situation"] + "\n\nTHEIR MEMORIES:\n"
                + "\n".join(f"{m['id']}: {m['text']}" for m in sheet["memories"]))
        reply = jparse(chat_complete("utility", JUDGE_SYSTEM, user, json_mode=True, temperature=0.0,
                                     max_tokens=4000, reasoning_effort="off")) or {}
        got = {str(k): int(v) for k, v in (reply.get("grades") or {}).items()
               if str(v).strip().lstrip("-").isdigit()}
        grades[beat] = got
        path.write_text(json.dumps(grades, indent=1), encoding="utf-8")
        print(f"beat {beat}: {len(got)} of {len(sheet['memories'])} graded")


def score(args):
    import numpy as np

    from core.db import q
    from mind.memory_common import _vec

    folder = Path(args.dir)
    packets = json.loads((folder / "packets.json").read_text())
    grades = json.loads(Path(args.grades).read_text())
    ids = sorted({m for pk in packets.values() for name in PACKETS for m in pk[name]})
    emb = {r["id"]: _vec(r["embedding"]) for r in q(
        f"SELECT id, embedding FROM memories WHERE id IN ({','.join('?' * len(ids))})", ids)}
    table = {name: {"mean": [], "2+": [], "3": [], "0": [], "rows": [], "dupes": []} for name in PACKETS}
    missing = 0
    for beat, pk in packets.items():
        g = grades.get(beat) or {}
        inverse = {mid: oid for oid, mid in pk["key"].items()}
        for name in PACKETS:
            vals = [g.get(inverse[m]) for m in pk[name]]
            missing += sum(v is None for v in vals)
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            table[name]["mean"].append(np.mean(vals))
            table[name]["2+"].append(sum(v >= 2 for v in vals))
            table[name]["3"].append(sum(v >= 3 for v in vals))
            table[name]["0"].append(sum(v == 0 for v in vals))
            table[name]["rows"].append(len(pk[name]))
            rows = [m for m in pk[name] if emb.get(m) is not None]
            table[name]["dupes"].append(sum(1 for a in range(len(rows)) for b in range(a + 1, len(rows))
                                            if float(emb[rows[a]] @ emb[rows[b]]) >= NEAR))
    print(f"{len(packets)} beats; grades from {args.grades}; {missing} packet rows ungraded")
    print(f"  {'packet':10} rows  mean grade  graded 2+ (per beat)  graded 3  graded 0  near-dup pairs")
    for name, t in table.items():
        print(f"  {name:10} {np.mean(t['rows']):4.1f}  {np.mean(t['mean']):10.2f}  {np.mean(t['2+']):9.1f}"
              f" ({np.mean(t['2+']) / np.mean(t['rows']):.0%})      {np.mean(t['3']):8.1f}  {np.mean(t['0']):8.1f}"
              f"  {np.mean(t['dupes']):14.1f}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p_build = sub.add_parser("build")
    p_build.add_argument("--labels", required=True)
    p_build.add_argument("--out", required=True)
    p_build.add_argument("--size", type=int, default=PACKET, help="rows per packet")
    p_judge = sub.add_parser("judge")
    p_judge.add_argument("--dir", required=True)
    p_score = sub.add_parser("score")
    p_score.add_argument("--dir", required=True)
    p_score.add_argument("--grades", required=True)
    args = parser.parse_args()
    {"build": build, "judge": judge, "score": score}[args.mode](args)


if __name__ == "__main__":
    main()
