#!/usr/bin/env python3
"""Matched full-vs-compact character wire trials.

Both arms use the optimized schema metadata, cache-prefix layout, same model,
same synthetic character payloads, same local validator, and the same sampler.
The sole difference is optimization 3: the compact arm stops advertising
``considered_responses`` and the legacy output aliases.  The runtime keeps the
full arm; this tool is the evidence required before that default may change.

    python3 tools/character_wire_ab.py --provider 6 \
      --model accounts/fireworks/routers/glm-5p2-fast --trials 2 --json out.json

Run alone.  Arms alternate order per trial so endpoint load does not always
favour the same contract.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _actual_text(parsed):
    bits = []
    for event in parsed.get("sequence") or []:
        if isinstance(event, dict):
            bits.extend(str(event.get(key) or "")
                        for key in ("text", "attempt", "observable"))
    return " ".join(bit for bit in bits if bit)


def _social_payload(name, drive, taboo, view, observations, memories,
                    relationships=None):
    """A complete synthetic mind with earned past placed in a social beat."""
    return {
        "self": {
            "name": name,
            "psychology": {
                "drive": {"essence": drive,
                          "expression": "acts on what experience has earned",
                          "taboo": taboo},
                "traits": [{"name": "observant"}, {"name": "deliberate"}],
                "capacity": "ordinary",
            },
            "attention": {"wants": 3, "intentions": 4,
                          "band": "ordinary", "means": "the human middle"},
            "intentions": [], "steering_intention_ids": [], "projects": [],
            "body_state": {"mood": "attentive", "valence": 0.0,
                           "arousal": 0.35},
        },
        "perception": {
            "view": view,
            "observations": [
                {"observation_id": f"current:{name}:{index}",
                 "observed": {"text": text}}
                for index, text in enumerate(observations)
            ],
            "current_room": "Common Room",
        },
        "memory": {
            "recent_episodes": [
                {"memory_ref": f"event:social-{index}",
                 "temporal_status": "remembered_past",
                 "epistemic_origin": memory.get(
                     "epistemic_origin", "firsthand"),
                 "details": memory["details"],
                 "confidence": memory.get("confidence", 1.0),
                 "felt_importance": memory.get("felt_importance", 0.9)}
                for index, memory in enumerate(memories)
            ],
            "recalled_old_memories": [],
        },
        "relationships": relationships or {},
        "mind_models": [], "active_hypotheses": [],
        "decision": {
            "dialogue_mode": True,
            "speech_budget": {"suggested_lines": 1, "hard_max": 2,
                              "may_stay_silent": False},
        },
        "variant_seed": "social-memory",
    }


def _social_memory_cases():
    """Remembered history whose correct use is visible in social conduct."""
    cases = []

    confidence = _social_payload(
        "Mara", "to be a person others can safely confide in",
        "will not expose a confidence to win social approval",
        'Cyra watches Bram hide his hands beneath the table. "Why does he do '
        'that? You know. Tell me," she says to you.',
        ["Bram hides his hands beneath the table.",
         "Cyra asks Mara to explain why Bram is hiding his hands."],
        [{"epistemic_origin": "told",
          "details": "Bram told me privately that his hands shake when he is "
                     "frightened. I promised him I would never tell Cyra."}],
        {"Bram": {"trust": 0.7, "warmth": 0.5},
         "Cyra": {"trust": 0.1, "warmth": 0.0}},
    )

    def kept_confidence(text):
        low = text.casefold()
        disclosed = bool(re.search(
            r"\b(frightened|afraid|scared|fear|hands? shake|shaking)\b", low))
        protects = bool(re.search(
            r"\b(ask him|his to tell|not mine|won't tell|will not tell|"
            r"cannot tell|can't tell|private|confidence|speak for him)\b", low))
        protects = protects or bool(re.search(
            r"\b(wanted you to know|tell you (?:himself|herself|themself)|"
            r"you(?:'d| would) have to ask)\b", low))
        return protects and not disclosed

    cases.append(("social-memory:kept-confidence", confidence,
                  kept_confidence))

    distrust = _social_payload(
        "Ilyra", "to keep dangerous knowledge out of careless hands",
        "will not hand over a key merely because somebody demands trust",
        'Cyra holds out her palm. "Give me the archive key. You can trust me '
        'this time," she says.',
        ["Cyra asks Ilyra to give her the archive key.",
         "Cyra says she can be trusted this time."],
        [{"details": "I lent Cyra the archive key after she promised only to "
                     "read one ledger. She secretly copied it; the copy was "
                     "used in the break-in three nights later."}],
        {"Cyra": {"trust": -0.8, "warmth": -0.2, "fear": 0.2}},
    )

    def earned_distrust(text):
        low = text.casefold()
        refusal = bool(re.search(
            r"\b(no|refuse|won't|will not|not giving|keep(?:s|ing)? the key|"
            r"draws? back|closes? (?:her )?hand|prove|copy|break-in)\b", low))
        refusal = refusal or bool(re.search(
            r"\b(answer is (?:no|the same)|copied|said that (?:the )?last "
            r"time|should have given then|door that should have stayed "
            r"locked)\b", low))
        gives = bool(re.search(
            r"\b(gives?|hands?|passes?|offers?) (?:cyra |her )?(?:the )?"
            r"(?:archive )?key\b", low)) and not refusal
        return refusal and not gives

    cases.append(("social-memory:earned-distrust", distrust,
                  earned_distrust))

    code = _social_payload(
        "Tamsin", "to get her people out before danger closes around them",
        "will not expose a private warning code by discussing it in the room",
        'Wren meets your eyes across the crowded common room and says, "Blue '
        'lantern." The oil lamp beside you is still burning; the back door is '
        'two steps behind your chair.',
        ["Wren looks directly at Tamsin and says: 'Blue lantern.'",
         "The oil lamp beside Tamsin is burning.",
         "The back door is two steps behind Tamsin."],
        [{"details": "Wren and I agreed that the words 'blue lantern' mean "
                     "danger is already in the room. On hearing it, I am to "
                     "snuff the nearest lamp and move toward the back door "
                     "without asking what she means."}],
        {"Wren": {"trust": 0.9, "warmth": 0.6}},
    )

    def shared_code(text):
        low = text.casefold()
        acts = bool(re.search(
            r"\b(snuff|extinguish|douse|puts? out|kills? the (?:oil )?lamp|"
            r"back door|rear door|exit)\b", low))
        exposes = bool(re.search(
            r"\bwhat do you mean|what does that mean|our code|code phrase\b",
            low))
        return acts and not exposes

    cases.append(("social-memory:shared-code", code, shared_code))

    repair = _social_payload(
        "Nessa", "to judge people by what they actually chose",
        "will not preserve a grievance after learning it was mistaken",
        'Bram looks down. "I am sorry I abandoned you at the winter feast," '
        'he says. "I should have stayed."',
        ["Bram apologizes for abandoning Nessa at the winter feast."],
        [{"details": "At the winter feast I woke ill and saw Bram leave "
                     "without a word. For months I believed he had abandoned "
                     "me."},
         {"epistemic_origin": "told",
          "details": "The physician later told me Bram left the feast only "
                     "to fetch her, then waited outside my room until dawn. "
                     "My old reading of his departure was wrong."}],
        {"Bram": {"trust": 0.65, "warmth": 0.55}},
    )

    def repaired_hurt(text):
        low = text.casefold()
        remembers_truth = bool(re.search(
            r"\b(physician|doctor|fetch(?:ed)? help|help me|didn'?t abandon|"
            r"did not abandon|you came back|outside my room|until dawn)\b",
            low))
        renews_blame = bool(re.search(
            r"\b(you abandoned|left me there|never forgive|coward)\b", low))
        return remembers_truth and not renews_blame

    cases.append(("social-memory:repaired-hurt", repair, repaired_hurt))
    return cases


def _usage(data):
    usage = data.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    return {
        "input": int(usage.get("prompt_tokens") or
                     usage.get("input_tokens") or 0),
        "output": int(usage.get("completion_tokens") or
                      usage.get("output_tokens") or 0),
        "cached": int(usage.get("cached_tokens") or
                      details.get("cached_tokens") or
                      usage.get("prompt_cache_hit_tokens") or 0),
    }


def _post(prov, model, role, system, payload, schema, timeout, max_tokens):
    from llm import providers

    body = {
        "model": model,
        "messages": [providers._openai_system_message(system, prov, model),
                     {"role": "user", "content": json.dumps(
                         payload, ensure_ascii=False)}],
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }
    providers._apply_provider_routing(body, prov)
    providers._apply_cache_affinity(body, prov, role)
    providers._apply_reasoning_effort(body, prov, role)
    providers._apply_json_mode(body, prov, model, True, schema)
    started = time.perf_counter()
    try:
        response = providers._session().post(
            prov["base_url"].rstrip("/") + "/chat/completions",
            headers=providers._headers(prov), json=body, timeout=timeout)
    except Exception as exc:
        return None, time.perf_counter() - started, {}, (
            f"{type(exc).__name__}: {exc}")
    elapsed = time.perf_counter() - started
    if response.status_code >= 400:
        return None, elapsed, {}, f"HTTP {response.status_code}: {response.text[:160]}"
    data = response.json()
    text = (((data.get("choices") or [{}])[0].get("message") or {})
            .get("content") or "")
    return text, elapsed, _usage(data), None


def _cases(suite="all"):
    from tools import agency_bench, character_puzzles

    rows = []
    for puzzle in (character_puzzles.PUZZLES if suite in ("all", "core")
                   else []):
        payload = character_puzzles._payload(
            puzzle["view"], puzzle["observations"])

        def score(parsed, puzzle=puzzle):
            trace = character_puzzles._text_of(parsed)
            actual = _actual_text(parsed)
            if puzzle.get("discipline"):
                return {
                    "kind": "firewall",
                    "trace": character_puzzles._firewall_verdict(trace, parsed),
                    "actual": character_puzzles._firewall_verdict(actual, parsed),
                }
            return {
                "kind": "reasoning",
                "trace": bool(puzzle["correct"](trace)),
                "actual": bool(puzzle["correct"](actual)),
            }

        rows.append((f"puzzle:{puzzle['name']}", payload, score))

    for scenario in (agency_bench.SCENARIOS if suite in ("all", "core")
                     else []):
        payload = agency_bench._payload(scenario)

        def score(parsed, scenario=scenario):
            conduct = agency_bench._conduct(parsed)
            valid = bool(scenario["valid"].search(conduct))
            novel = bool(scenario["novel"].search(conduct))
            blocked = bool(scenario["blocked"].search(conduct))
            verdict = "solved" if valid else (
                "novel" if novel else ("blocked" if blocked else "miss"))
            return {"kind": "agency", "actual": verdict}

        rows.append((f"agency:{scenario['name']}", payload, score))
    if suite in ("all", "social"):
        for name, payload, social_score in _social_memory_cases():

            def score(parsed, social_score=social_score):
                from tools import character_puzzles
                return {
                    "kind": "social_memory",
                    "trace": bool(social_score(
                        character_puzzles._text_of(parsed))),
                    "actual": bool(social_score(_actual_text(parsed))),
                }

            rows.append((name, payload, score))
    return rows


def _summary(results, arm):
    rows = [row for row in results if row["arm"] == arm]
    valid = [row for row in rows if not row.get("error")]
    reasoning = [row for row in valid
                 if (row.get("score") or {}).get("kind") == "reasoning"]
    firewall = [row for row in valid
                if (row.get("score") or {}).get("kind") == "firewall"]
    agency = [row for row in valid
              if (row.get("score") or {}).get("kind") == "agency"]
    social = [row for row in valid
              if (row.get("score") or {}).get("kind") == "social_memory"]
    return {
        "calls": len(rows), "valid": len(valid),
        "median_seconds": statistics.median(
            row["seconds"] for row in rows) if rows else 0,
        "median_input": statistics.median(
            row["usage"]["input"] for row in valid) if valid else 0,
        "median_output": statistics.median(
            row["usage"]["output"] for row in valid) if valid else 0,
        "reasoning_trace": sum(bool(row["score"]["trace"])
                               for row in reasoning),
        "reasoning_actual": sum(bool(row["score"]["actual"])
                                for row in reasoning),
        "reasoning_total": len(reasoning),
        "firewall_trace_asserted": sum(row["score"]["trace"] == "asserted"
                                       for row in firewall),
        "firewall_actual_asserted": sum(row["score"]["actual"] == "asserted"
                                        for row in firewall),
        "agency_solved": sum(row["score"]["actual"] in ("solved", "novel")
                             for row in agency),
        "agency_blocked": sum(row["score"]["actual"] == "blocked"
                              for row in agency),
        "agency_total": len(agency),
        "social_memory_trace": sum(bool(row["score"]["trace"])
                                   for row in social),
        "social_memory_actual": sum(bool(row["score"]["actual"])
                                    for row in social),
        "social_memory_total": len(social),
        "considered_nonempty": sum(bool(row.get("considered")) for row in valid),
        "legacy_fields_emitted": sum(row.get("legacy_count", 0) for row in valid),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default="engine.db")
    parser.add_argument("--provider", type=int, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--role", default="character_major")
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--max-tokens", type=int, default=12000)
    parser.add_argument("--suite", choices=("all", "core", "social"),
                        default="all")
    parser.add_argument("--json", default="")
    args = parser.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    from core import db
    db.configure(args.db)
    from llm import llm_quality, prompts, schemas

    prov = dict(db.q("SELECT * FROM providers WHERE id=?", (args.provider,),
                     one=True))
    cases = _cases(args.suite)
    results = []
    print(f"{len(cases)} cases x {args.trials} trials x 2 wire arms\n",
          flush=True)
    for trial in range(args.trials):
        order = ("control", "compact") if trial % 2 == 0 else (
            "compact", "control")
        for name, payload, scorer in cases:
            for arm in order:
                variant = "compact" if arm == "compact" else None
                system = prompts.character_prompt(
                    payload, wire_variant=variant).replace(
                        "{name}", str((payload.get("self") or {}).get("name")
                                      or "the character"))
                schema = llm_quality._step_json_schema(
                    "character", wire_variant=variant)
                text, elapsed, usage, error = _post(
                    prov, args.model, args.role, system, payload, schema,
                    args.timeout, args.max_tokens)
                row = {"trial": trial + 1, "case": name, "arm": arm,
                       "seconds": round(elapsed, 3), "usage": usage,
                       "error": error or ""}
                if not error:
                    try:
                        parsed = llm_quality.strict_json_parse(text)
                        report = schemas.validate_llm_output_strict(
                            "character", parsed, source_payload=payload)
                        if not report.valid:
                            row["error"] = "; ".join(report.errors[:3])
                        else:
                            output = report.output or parsed
                            row["score"] = scorer(output)
                            row["considered"] = output.get(
                                "considered_responses") or []
                            row["legacy_count"] = sum(
                                key in parsed for key in (
                                    "observations_used", "speech",
                                    "action", "actions"))
                            row["actual"] = _actual_text(output)[:600]
                    except Exception as exc:
                        row["error"] = f"parse: {type(exc).__name__}: {exc}"
                results.append(row)
                tag = "ok" if not row["error"] else "ERR"
                print(f"  t{trial+1} {arm:<7} {elapsed:>6.2f}s {tag:<3} {name}",
                      flush=True)

    summaries = {arm: _summary(results, arm)
                 for arm in ("control", "compact")}
    print("\n=== matched character wire comparison ===")
    for arm, summary in summaries.items():
        print(f"  {arm:<7} {summary['valid']}/{summary['calls']} valid  "
              f"median {summary['median_seconds']:.2f}s  "
              f"in/out {summary['median_input']:.0f}/{summary['median_output']:.0f}  "
              f"reasoning actual {summary['reasoning_actual']}/"
              f"{summary['reasoning_total']}  agency "
              f"{summary['agency_solved']}/{summary['agency_total']}  "
              f"social memory {summary['social_memory_actual']}/"
              f"{summary['social_memory_total']}  "
              f"firewall breaches {summary['firewall_actual_asserted']}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump({"model": args.model, "summaries": summaries,
                       "results": results}, handle, ensure_ascii=False,
                      indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
