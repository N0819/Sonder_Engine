"""Can retrieval answer a question a character asks its own memory?

An experiment instrument for `docs/design/DESIGN_JEV_CHARACTER_PASS.md`
(2026-09-26). The owner: "can our RRF actually pull up question relevant
answers in its current state? What might we need to adjust so it can?"

The engine's question-shaped recall is the PONDER lane: a character sets
`{type:'ponder', query, why}` on one beat and `memory_context` answers it on
the next through `search_memories(query)` -- the same fused ranking as passive
recall, with no aspects, returning `max(4, recall_limit)` rows.

`write` mode, per beat: the character's own situation (perception view, mood,
goal, concerns, drive, values) goes to the `utility` model, which writes three
ponders under the prompt's own contract -- one about something known of
someone or something, one about an earlier moment this one resembles, one
about whether something has happened or changed recently. `--real` adds every
ponder the chat actually holds for the character, answered on the beat after
it was set, as the engine answers it.

`label` mode, per question: Jev grades the WHOLE visible bank ("How much does
this memory help answer the question ...", graded) -- the answer key -- and
every candidate net's full ranking is cached: today's ponder lane in fused
order and as shipped (diversity pass on, k 8 and 24); the same seam given the
`why` and a hypothetical answer as aspects; and the separate generators
(meaning, cue and keyword for the question, the question with its why, an
instruction-prefixed question, three hypothetical memories written by the
`utility` model, the situation, recency, importance).

`score` mode: recall of each question's top 5 (and top 10) by Jev at 5, 8,
24, 50 and 100, per net, over the questions some memory actually answers.

Usage:
    ENGINE_DB=<a copy> python tools/jev_question_recall.py write --chat 63 --char 35 \\
        --turns 1847,1851 --out q63.json
    ENGINE_DB=<a copy> python tools/jev_question_recall.py write --chat 72 --char 58 --real --out q63.json
    ENGINE_DB=<a copy> python tools/jev_question_recall.py label --questions q63.json --out ql63.json
    python tools/jev_question_recall.py score --labels ql63.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

WRITE_SYSTEM = """You are {name}, a character in an ongoing story. Below is what you perceive right now, how you feel, what you are trying to do and what is still unsettled for you.

You can set a private recall request: a concrete question whose answer matters to your next decision, or to recall something specific. Nobody sees or hears it; your own memory answers it.

Write three such requests you might plausibly make at this moment, each about a different subject:
1. something you know or learned about someone or something that matters here;
2. an earlier moment that this one resembles or brings back;
3. whether something has happened, changed or been said recently.

Write each the way you would ask it yourself (at most 240 characters), with why it matters to you now (at most 240 characters). Return JSON only: {{"ponders": [{{"kind": 1, "query": "...", "why": "..."}}, {{"kind": 2, ...}}, {{"kind": 3, ...}}]}}"""

HYDE_SYSTEM = """A person is searching their own memory. Given their question and their situation, write three short memories that would answer it, as their memory would have stored them. Match the FORM of the example rows -- they show how this memory writes things down, not what happened; do not copy their content. Each memory at most 300 characters. Return JSON only: {"memories": ["...", "...", "..."]}"""

INSTRUCT = "Instruct: Given a question a person asks their own memory, retrieve the memories that answer it\nQuery: "
ANSWER = "How much does this memory help answer the question you are asking your own memory: \"{query}\"?"
KIND_NAMES = {1: "known", 2: "resembles", 3: "recent", 0: "real"}


def _llm_json(system, user):
    from agents.common import jparse
    from llm.providers import chat_complete

    raw = chat_complete("utility", system, user, json_mode=True, max_tokens=3000,
                        temperature=0.7, reasoning_effort="off")
    return jparse(raw) or {}


def _inputs(chat_id, char_id, turn_id, cutoff_idx=None):
    import jev_net_labels as labels
    import jev_net_recall as recall
    from core.db import q

    inputs = recall.beat(chat_id, char_id, turn_id)
    idx = q("SELECT idx FROM turns WHERE id=?", (turn_id,), one=True)["idx"]
    active = labels.state_entering(chat_id, char_id, idx)
    if active:
        concerns = active.get("active_concerns") or []
        inputs.update(goal=str(active.get("goal") or ""), mood=str(active.get("mood") or ""),
                      concerns=" ".join(str(c.get("text") if isinstance(c, dict) else c) for c in concerns))
    if cutoff_idx is not None:
        inputs["turn_idx"] = cutoff_idx
    return inputs


def real_ponders(chat_id, char_id):
    """Every distinct ponder this character set in this chat, with the turn
    the engine answers it on (the next one) -- or the setting turn with the
    next turn's cutoff when the chat stops there."""
    from core.db import q

    found = []
    rows = q("SELECT t.id, t.idx, s.key, v.content FROM steps s JOIN variants v ON v.step_id=s.id "
             "JOIN turns t ON t.id=s.turn_id WHERE t.chat_id=? AND v.active=1 AND "
             "(s.key='interaction_loop' OR s.key=?) AND v.content LIKE '%ponder%' ORDER BY t.idx",
             (chat_id, f"character:{char_id}"))
    for row in rows:
        data = json.loads(row["content"])
        results = ([r.get("result") or {} for r in data.get("rounds") or []]
                   if row["key"] == "interaction_loop" else [data])
        for res in results:
            ponder = res.get("ponder") if isinstance(res, dict) else None
            if (isinstance(ponder, dict) and str(ponder.get("query") or "").strip()
                    and str(res.get("char_id") or char_id) == str(char_id)):
                nxt = q("SELECT id FROM turns WHERE chat_id=? AND idx=?", (chat_id, row["idx"] + 1), one=True)
                found.append({"turn_id": nxt["id"] if nxt else row["id"], "cutoff_idx": row["idx"] + 1,
                              "set_turn_id": row["id"], "query": ponder["query"], "why": ponder.get("why") or "",
                              "kind": 0})
    seen, out = set(), []
    for item in found:
        if item["query"] not in seen:
            seen.add(item["query"])
            out.append(item)
    return out


def write(args):
    import jev_memory_probe as probe

    out = Path(args.out)
    data = json.loads(out.read_text()) if out.exists() else {"questions": []}
    # By text alone: a branch carries its parent's ponders verbatim.
    have = {qq["query"] for qq in data["questions"]}
    if args.real:
        for item in real_ponders(args.chat, args.char):
            if item["query"] not in have:
                data["questions"].append({"chat": args.chat, "char": args.char, **item})
    for turn_id in [int(t) for t in (args.turns or "").split(",") if t.strip()]:
        if any(qq["turn_id"] == turn_id and qq["kind"] for qq in data["questions"]):
            continue
        inputs = _inputs(args.chat, args.char, turn_id)
        reply = _llm_json(WRITE_SYSTEM.format(name=inputs["name"]), probe.state_for(inputs))
        for ponder in (reply.get("ponders") or [])[:3]:
            query = " ".join(str(ponder.get("query") or "").split())[:240]
            if query:
                data["questions"].append({
                    "chat": args.chat, "char": args.char, "turn_id": turn_id, "cutoff_idx": None,
                    "query": query, "why": " ".join(str(ponder.get("why") or "").split())[:240],
                    "kind": int(ponder.get("kind") or 0) or 9})
        out.write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"turn {turn_id}: {len(reply.get('ponders') or [])} ponders")
    out.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"{len(data['questions'])} questions in {out}")


def hypothetical(inputs, question, memories):
    """Three memories the `utility` model expects would answer the question,
    in the form of three of the character's own rows (one per provenance)."""
    rng = random.Random(question["query"])
    by_prov = {}
    for mem in memories.values():
        by_prov.setdefault(mem.get("provenance") or "", []).append(mem)
    examples = [rng.choice(rows) for _p, rows in sorted(by_prov.items()) if rows][:4]
    user = (f"Who: {inputs['name']}\nTheir situation (excerpt): {inputs['view'][:900]}\n"
            f"What they are trying to do: {inputs['goal'] or 'nothing in particular'}\n\n"
            f"Question: {question['query']}\nWhy: {question['why']}\n\n"
            "Example rows from this person's memory (form only):\n"
            + "\n".join("- " + " ".join(str(m.get("content") or "").split())[:300] for m in examples))
    reply = _llm_json(HYDE_SYSTEM, user)
    return [" ".join(str(m).split())[:300] for m in (reply.get("memories") or []) if str(m).strip()][:3]


def label_question(question):
    import jev_memory_probe as probe
    import jev_net_recall as recall
    from mind import memory_retrieval as retrieval

    inputs = _inputs(question["chat"], question["char"], question["turn_id"], question.get("cutoff_idx"))
    situation = inputs["view"]
    from mind.memory_read import visible_memory_rows
    from mind.memory_write import _row_memory

    qtext, why = question["query"], question["why"]
    rows = visible_memory_rows(inputs["chat_id"], inputs["char_id"], before_turn_idx=inputs["turn_idx"],
                               viewer_frame_id=None, include_archived=True)
    memories = {m["id"]: m for m in (_row_memory(r) for r in rows)}
    hyde = question.get("hyde") or hypothetical(inputs, question, memories)

    # The answer key: Jev over the whole bank, the question quoted with each memory.
    state = probe.state_for(inputs) + f"\n\nTHE QUESTION YOU ARE ASKING YOUR OWN MEMORY: {qtext}\nWHY IT MATTERS NOW: {why}"
    jq = {str(mid): {"type": "choice",
                     "instructions": ANSWER.format(query=qtext) + "\n\n" + probe.memory_text(mem, inputs["turn_idx"]),
                     "criteria": {key: label for key, (label, _w) in probe.SCALE.items()}}
          for mid, mem in memories.items()}
    grades, seconds, _raw = probe.ask_jev(state, jq)

    # Generators: the question is the main query; everything else is an aspect lane.
    q_inputs = dict(inputs, view=qtext)
    aspects = [("why", why), ("question+why", f"{qtext} {why}"), ("instructed", INSTRUCT + qtext),
               ("situation", situation[:3000])] + [(f"hyde:{i}", h) for i, h in enumerate(hyde)]
    aspects = [(label, text) for label, text in aspects if str(text or "").strip()]
    _mems, ranks = recall.generators(q_inputs, aspects)
    ranks = {("question:" + k if k in ("semantic", "cue", "keyword") else k): v for k, v in ranks.items()}
    for label, text in (("keyword:question+why", f"{qtext} {why}"), ("keyword:hyde", " ".join(hyde))):
        ranks[label] = [mid for mid in retrieval._lexical_memory_ranking(
            inputs["chat_id"], inputs["char_id"], text, limit=len(memories)) if mid in memories]

    # Today's ponder lane through the production seam: fused order (diversity
    # pass replaced), and as shipped (diversity pass on) at k 8 and 24.
    nets = {"ponder today (fused)": [r["id"] for r in probe.net(dict(inputs), qtext, len(memories), None)],
            "seam: question + why aspect": [r["id"] for r in probe.net(
                dict(inputs), qtext, len(memories), [("why", why)])],
            "seam: question + why + hypothetical aspects": [r["id"] for r in probe.net(
                dict(inputs), qtext, len(memories), [("why", why)] + [(f"expected {i}", h) for i, h in enumerate(hyde)])]}
    shipped = {}
    for k in (8, 24):
        got = retrieval.search_memories(inputs["chat_id"], inputs["char_id"], qtext, k=k, include_archived=True,
                                        current_turn_idx=inputs["turn_idx"], viewer_frame_id=None,
                                        chronological=True, record_access=False)
        shipped[str(k)] = [r["id"] for r in got]
    return {**question, "turn_idx": inputs["turn_idx"], "bank": len(memories), "hyde": hyde,
            "jev_seconds": seconds, "judged": {mid: round(v, 4) for mid, v in grades.items() if v is not None},
            "ranks": ranks, "nets": nets, "shipped": shipped}


def label(args):
    src = json.loads(Path(args.questions).read_text())["questions"]
    out = Path(args.out)
    data = json.loads(out.read_text()) if out.exists() else {"labels": []}
    done = {(x["chat"], x["char"], x["query"]) for x in data["labels"]}
    todo = [qq for qq in src if (qq["chat"], qq["char"], qq["query"]) not in done]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for item in pool.map(label_question, todo):
            data["labels"].append(item)
            out.write_text(json.dumps(data), encoding="utf-8")
            top = max(item["judged"].values()) if item["judged"] else 0
            print(f"chat {item['chat']} idx {item['turn_idx']} bank {item['bank']} kind {item['kind']} "
                  f"top {top:.2f} jev {item['jev_seconds']}s | {item['query'][:70]}")


def score(args):
    import jev_net_recall as recall

    data = json.loads(Path(args.labels).read_text())["labels"]
    if args.kind:
        data = [item for item in data if KIND_NAMES.get(item["kind"]) == args.kind]
    at = (5, 8, 24, 50, 100)
    table, answered = {}, 0
    for item in data:
        judged = {int(k): v for k, v in item["judged"].items()}
        if not judged or max(judged.values()) < args.floor:
            continue
        answered += 1
        ref = sorted(judged, key=lambda mid: -judged[mid])[:args.top]
        ranks = {name: [int(m) for m in r] for name, r in item["ranks"].items()}
        nets = {name: [int(m) for m in order] for name, order in item["nets"].items()}
        hyde_lanes = {k: v for k, v in ranks.items() if k.startswith("aspect:hyde:")}
        nets["question: meaning only"] = ranks["question:semantic"]
        nets["question: keyword only"] = ranks["question:keyword"]
        nets["question+why: meaning"] = ranks["aspect:question+why"]
        nets["instructed question: meaning"] = ranks["aspect:instructed"]
        nets["hypothetical answers: meaning"] = recall.union_net(hyde_lanes, len(judged)) if hyde_lanes else []
        nets["union: question lanes + hypothetical + recency"] = recall.union_net(
            {k: ranks[k] for k in ranks if k.startswith(("question:", "aspect:hyde:", "aspect:question+why",
                                                          "keyword:", "recency"))}, len(judged))
        for name, order in nets.items():
            for n in at:
                table.setdefault(name, {}).setdefault(n, []).append(
                    sum(1 for mid in ref if mid in set(order[:n])) / len(ref))
        for k, got in item["shipped"].items():
            table.setdefault(f"ponder today AS SHIPPED, k={k}", {}).setdefault(int(k), []).append(
                sum(1 for mid in ref if mid in set(int(m) for m in got)) / len(ref))
    print(f"{answered} of {len(data)} questions have a memory graded >= {args.floor}; "
          f"reference = Jev's top {args.top}")
    for name, row in table.items():
        print(f"  {name:48} " + "  ".join(f"@{n}: {sum(v) / len(v):.0%}" for n, v in sorted(row.items())))
    # How peaked is the answer key? Grades at ranks 1/5/10/20, per kind.
    by_kind = {}
    for item in data:
        grades = sorted((float(v) for v in item["judged"].values()), reverse=True)
        if len(grades) >= 20:
            by_kind.setdefault(KIND_NAMES.get(item["kind"], str(item["kind"])), []).append(
                [grades[0], grades[4], grades[9], grades[19]])
    print("answer-key grades at rank 1 / 5 / 10 / 20 (median), by kind:")
    for kind, rows in sorted(by_kind.items()):
        med = [sorted(col)[len(col) // 2] for col in zip(*rows)]
        print(f"  {kind:10} n={len(rows):2}  " + " / ".join(f"{v:.2f}" for v in med))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p_write = sub.add_parser("write")
    p_write.add_argument("--chat", type=int, required=True)
    p_write.add_argument("--char", type=int, required=True)
    p_write.add_argument("--turns", default="")
    p_write.add_argument("--real", action="store_true")
    p_write.add_argument("--out", required=True)
    p_label = sub.add_parser("label")
    p_label.add_argument("--questions", required=True)
    p_label.add_argument("--out", required=True)
    p_label.add_argument("--workers", type=int, default=3)
    p_score = sub.add_parser("score")
    p_score.add_argument("--labels", required=True)
    p_score.add_argument("--top", type=int, default=5)
    p_score.add_argument("--floor", type=float, default=0.5)
    p_score.add_argument("--kind", default="", help="known | resembles | recent | real")
    args = parser.parse_args()
    {"write": write, "label": label, "score": score}[args.mode](args)


if __name__ == "__main__":
    main()
