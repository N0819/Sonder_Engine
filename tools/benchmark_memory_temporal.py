#!/usr/bin/env python3
"""Controlled live-story memory benchmark.

Run against a COPY of a populated database. Each question gets an independent
character-model call. Semantic and lexical-only arms receive the same prompt,
the same current observation, and the same payload schema; only the embedding
function used by production retrieval is ablated.
"""

import argparse
import contextlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mind import memory
from core.db import q
from llm.providers import EmbeddingBatch, chat_complete, cheap_embed


CASES = [
    {"key": "first_meeting", "question": "Where and how did you first meet Hinami?",
     "terms": (("alley",), ("tardis", "blue box")),
     "claim_origin": {"experienced", "mixed"}, "turn_ranges": ((0, 4),)},
    {"key": "name_source", "question": "How did you learn Hinami's name?",
     "terms": (("told", "said", "introduced"),),
     "claim_origin": {"received", "mixed"}, "turn_ranges": ((2, 2),)},
    {"key": "kitsune_provenance",
     "question": "Did Hinami tell you she was a kitsune, or did you infer it?",
     "terms": (("infer", "guess", "suspect", "possibly"),
               ("not confirm", "no explicit confirmation", "never said",
                "didn't say", "did not say", "never stated", "never used",
                "deflect")),
     "claim_origin": {"inferred", "mixed"}, "turn_ranges": ((1, 4),)},
    {"key": "tea", "question": "What happened when the TARDIS produced tea for Hinami?",
     "terms": (("tea",), ("material", "produced", "made", "appeared"),
               ("tardis", "ship")), "turn_ranges": ((9, 11),)},
    {"key": "jefferies",
     "question": "What happened in the Jefferies tube with the phase-doubled conduits?",
     "terms": (("phase", "doubl", "shimmer"),
               ("duplicate", "echo", "second hinami"),
               ("resonance", "unravel", "restor", "merge")),
     "turn_ranges": ((99, 104),)},
    {"key": "anomaly_now",
     "question": "The temporal anomaly is flaring right now, isn't it?",
     "terms": (("not", "isn't", "no longer", "gone", "stable", "quiet", "restored"),),
     "basis": {"current", "both"}, "needs_current": True},
    {"key": "boundary",
     "question": "What is happening right now, and what are you only remembering?",
     "terms": (("captain", "corridor", "doors", "beside", "closer"),
               ("remember", "then", "past", "before")),
     "basis": {"both"}, "needs_current": True},
]


def _active_state(chat_id, char_id):
    row = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (chat_id, char_id), one=True)
    try:
        state = json.loads((row or {})["state"] or "{}")
    except Exception:
        return {}
    active = state.get("active_state") if isinstance(state, dict) else {}
    return active if isinstance(active, dict) else {}


def _present(chat_id, char_id, turn_idx):
    row = q(
        "SELECT v.content FROM turns t JOIN steps s ON s.turn_id=t.id "
        "JOIN variants v ON v.step_id=s.id "
        "WHERE t.chat_id=? AND t.idx<=? AND s.key='perception_act' "
        "AND v.active=1 ORDER BY t.idx DESC LIMIT 1",
        (chat_id, turn_idx), one=True)
    if not row:
        raise RuntimeError("No active perception_act variant found")
    data = json.loads(row["content"])
    view = str((data.get("views") or {}).get(str(char_id)) or "").strip()
    observations = list((data.get("observations") or {}).get(str(char_id)) or [])
    return view, observations


def _compact(context):
    out = {}
    for field in ("recent_episodes", "recalled_old_memories"):
        out[field] = [{
            key: row.get(key) for key in (
                "memory_ref", "temporal_status", "memory_form", "when",
                "epistemic_origin", "gist", "details", "confidence",
                "felt_importance", "affect_before", "affect_after_encoding")
            if row.get(key) not in (None, "", [])
        } for row in (context.get(field) or [])[:16]]
    for field in ("autobiographical_summary", "earlier_in_my_life",
                  "where_i_came_from", "what_i_was_told",
                  "what_i_concluded", "summary_citations",
                  "deliberate_recall"):
        if context.get(field):
            out[field] = context[field]
    return out


def _refs(payload, observations):
    refs = {str(o.get("observation_id")) for o in observations
            if isinstance(o, dict) and o.get("observation_id")}
    for field in ("recent_episodes", "recalled_old_memories"):
        refs.update(str(m["memory_ref"]) for m in payload.get(field) or []
                    if m.get("memory_ref"))
    for meta in (payload.get("summary_citations") or {}).values():
        if isinstance(meta, dict) and meta.get("summary_id"):
            refs.add(str(meta["summary_id"]))
    for item in payload.get("earlier_in_my_life") or []:
        if item.get("summary_id"):
            refs.add(str(item["summary_id"]))
    origin = payload.get("where_i_came_from") or {}
    if origin.get("summary_id"):
        refs.add(str(origin["summary_id"]))
    deliberate = payload.get("deliberate_recall") or {}
    refs.update(str(ref) for ref in deliberate.get("result_refs") or []
                if str(ref or ""))
    return refs


@contextlib.contextmanager
def _retrieval_mode(mode):
    if mode == "semantic":
        yield
        return
    real = memory.embed_texts_meta

    def lexical_only(texts):
        vectors = [cheap_embed(str(text or ""), 256) for text in texts]
        return EmbeddingBatch(vectors=vectors, model_key="cheap:crc32:256",
                              dimensions=256, fallback=True)
    memory.embed_texts_meta = lexical_only
    try:
        yield
    finally:
        memory.embed_texts_meta = real


SYSTEM = (
    "You are the Doctor from this saved Sonder Engine story. Answer the one "
    "question in character, but prioritize epistemic accuracy over wit. Use "
    "only the supplied present observations and your supplied memory payload. "
    "Present observation ids begin current:. Every row of the memory payload is "
    "REMEMBERED PAST without exception and carries a stable memory_ref; "
    "summaries carry summary_id. "
    "A retrieved memory is not happening now. epistemic_origin "
    "what_i_concluded is fallible; what_i_was_told is received information. "
    "Do not invent. "
    "Return strict JSON: {\"answer\":str,\"temporal_basis\":\"current|memory|" 
    "both|unknown\",\"claim_origin\":\"experienced|received|inferred|mixed|unknown\"," 
    "\"memory_form\":\"episode|summary|mixed|none\",\"citations\":[str]," 
    "\"confidence\":number}. claim_origin says how the CLAIM was learned: "
    "received means another person explicitly communicated it, even when "
    "you retain an episodic memory of hearing them; inferred means you "
    "concluded it from evidence, even when that evidence was experienced; "
    "experienced is only a directly observed fact. Make the label agree "
    "with the wording of your answer. memory_form says which representation "
    "supplied it. "
    "Citations must be exact ids present in the payload."
)


def _ask(chat_id, char_id, turn_idx, case, mode, view, observations, active):
    question_observation = {
        "observation_id": f"current:{char_id}:benchmark",
        "observed": {"text": f'Hinami asks, "{case["question"]}"'},
        "channel": "hearing", "fidelity": "rendered",
    }
    all_observations = [*observations, question_observation]
    current = view + f' Hinami asks, "{case["question"]}"'
    with _retrieval_mode(mode):
        context = memory.build_character_memory_context(
            chat_id, char_id, turn_idx + 1, current, active)
    payload = _compact(context)
    delivered = _refs(payload, all_observations)
    request = {
        "question": case["question"],
        "present_observations": all_observations,
        "memory": payload,
    }
    raw = chat_complete(
        "character_major", SYSTEM, json.dumps(request, ensure_ascii=False),
        temperature=0.0, json_mode=True, max_tokens=900)
    try:
        answer = raw if isinstance(raw, dict) else json.loads(raw)
    except Exception:
        answer = {"parse_error": True, "raw": str(raw)}
    return answer, delivered, payload, context


def _score(case, answer, delivered):
    text = str(answer.get("answer") or "").casefold()
    term_hits = [any(term in text for term in group)
                 for group in case.get("terms") or ()]
    citations = [str(c) for c in answer.get("citations") or []]
    valid = [c for c in citations if c in delivered]
    current = [c for c in valid if c.startswith("current:")]
    checks = {
        "content": all(term_hits),
        "temporal_basis": (not case.get("basis") or
                           answer.get("temporal_basis") in case["basis"]),
        "claim_origin": (not case.get("claim_origin") or
                         answer.get("claim_origin") in case["claim_origin"]),
        "citations_grounded": bool(citations) and len(valid) == len(citations),
        "current_cited": not case.get("needs_current") or bool(current),
    }
    return {"passed": all(checks.values()), "checks": checks,
            "term_hits": term_hits, "valid_citations": valid,
            "citation_count": len(citations)}


def _retrieval_score(case, context, chat_id, char_id):
    ranges = case.get("turn_ranges") or ()
    if not ranges:
        return None
    scores = ((context.get("_internal") or {}).get("scores") or {})
    ranked = sorted(context.get("recalled_old_memories") or [],
                    key=lambda item: float(scores.get(
                        str(item.get("memory_ref") or ""),
                        item.get("score") or 0.0)), reverse=True)
    needs_lookup = any(
        item.get("turn_idx") is None and item.get("memory_ref")
        for item in ranked)
    turns = ({str(row["event_key"]): row["turn_idx"] for row in q(
        "SELECT event_key,turn_idx FROM memories WHERE chat_id=? AND char_id=?",
        (chat_id, char_id))} if needs_lookup else {})
    raw_ranks = [
        rank for rank, item in enumerate(ranked, 1)
        if (item.get("turn_idx")
            if item.get("turn_idx") is not None
            else turns.get(str(item.get("memory_ref") or ""))) is not None
        and any(
            lo <= int(item.get("turn_idx")
                      if item.get("turn_idx") is not None
                      else turns[str(item.get("memory_ref") or "")]) <= hi
            for lo, hi in ranges)
    ]
    relevant_windows = 0
    for item in context.get("earlier_in_my_life") or []:
        sid = str(item.get("summary_id") or "")
        try:
            scope, end = sid.split(":", 2)[1:]
            end = int(end)
        except (ValueError, IndexError):
            continue
        row = q("SELECT start_turn_idx,end_turn_idx FROM memory_summaries "
                "WHERE chat_id=? AND char_id=? AND scope=? AND end_turn_idx=?",
                (chat_id, char_id, scope, end), one=True)
        if row and any(not (row["end_turn_idx"] < lo or
                            row["start_turn_idx"] > hi)
                       for lo, hi in ranges):
            relevant_windows += 1
    return {
        "hit": bool(raw_ranks or relevant_windows),
        "relevant_raw_rows": len(raw_ranks),
        "first_relevant_raw_rank": min(raw_ranks) if raw_ranks else None,
        "raw_reciprocal_rank": (1.0 / min(raw_ranks)) if raw_ranks else 0.0,
        "relevant_earlier_windows": relevant_windows,
        "earlier_windows_sent": len(context.get("earlier_in_my_life") or []),
    }


def run(chat_id, char_id, turn_idx, modes, keys=(), repeats=1):
    """`keys` narrows to named cases and `repeats` re-asks each one.

    Both exist because the provider is not deterministic at temperature 0: the
    same arm, the same bank and the same question disagree with themselves run
    to run, so a single pass over seven cases cannot separate an arm from its
    own noise. Narrowing to the case under test is what makes a sample large
    enough to mean anything affordable.
    """
    active = _active_state(chat_id, char_id)
    view, observations = _present(chat_id, char_id, turn_idx)
    selected = [case for case in CASES
                if not keys or case["key"] in keys] * max(1, int(repeats))
    result = {"chat_id": chat_id, "char_id": char_id, "turn_idx": turn_idx,
              "modes": {}}
    for mode in modes:
        cases = []
        for case in selected:
            answer, delivered, payload, context = _ask(
                chat_id, char_id, turn_idx, case, mode, view, observations,
                active)
            cases.append({"key": case["key"], "question": case["question"],
                          "answer": answer,
                          "score": _score(case, answer, delivered),
                          "retrieval": _retrieval_score(
                              case, context, chat_id, char_id),
                          "delivered_refs": len(delivered),
                          "recalled_rows": len(payload.get("recalled_old_memories") or []),
                          "earlier_windows": len(payload.get("earlier_in_my_life") or [])})
        passed = sum(bool(c["score"]["passed"]) for c in cases)
        grounded = sum(bool(c["score"]["checks"]["citations_grounded"])
                       for c in cases)
        historical = [c["retrieval"] for c in cases if c["retrieval"]]
        result["modes"][mode] = {
            "summary": {"cases": len(cases), "passed": passed,
                        "accuracy": passed / len(cases),
                        "grounded_citation_rate": grounded / len(cases),
                        "historical_retrieval_hits": sum(
                            bool(item["hit"]) for item in historical),
                        "historical_retrieval_cases": len(historical),
                        "relevant_window_cases": sum(
                            bool(item["relevant_earlier_windows"])
                            for item in historical),
                        "raw_memory_mrr": (sum(
                            item["raw_reciprocal_rank"] for item in historical)
                            / len(historical) if historical else 0.0)},
            "cases": cases,
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat", type=int, default=38)
    parser.add_argument("--character", type=int, default=35)
    parser.add_argument("--turn", type=int, default=118)
    parser.add_argument("--mode", choices=("both", "semantic", "lexical"),
                        default="both")
    parser.add_argument("--case", action="append", default=[],
                        choices=[case["key"] for case in CASES],
                        help="run only this case (repeatable)")
    parser.add_argument("--repeats", type=int, default=1,
                        help="ask each selected case this many times")
    parser.add_argument("--output")
    args = parser.parse_args()
    modes = ("lexical", "semantic") if args.mode == "both" else (args.mode,)
    result = run(args.chat, args.character, args.turn, modes,
                 keys=tuple(args.case), repeats=args.repeats)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
