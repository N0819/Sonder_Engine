#!/usr/bin/env python3
"""Which director is fastest on a payload the size the Director really gets.

`tools/contract_bench.py` sends a 927-character payload and reported
Qwen3.6-35B-A3B at 3.95s. The same model, same role, in a live turn: 47.4s a
call. The gap is not the model -- it is the payload. Live director calls in a
three-cast chat measured 27,254 and 27,433 system tokens; the contract bench
was sending about 4,400. Six times too small, and it mis-ranked the single most
expensive role in the pipeline.

So this builds the payload from a REAL chat: its actual scene blob (rooms,
entities, positions, contacts, containment, attire, scales), its actual cast,
and its actual recent turns. No synthetic filler -- padding with lorem would
measure prompt LENGTH, and what costs time is length AND structure, since the
model has to parse a scene graph before it can reason about it.

    python3 tools/director_shootout.py --chat 9 --models a,b,c
    python3 tools/director_shootout.py --chat 9 --models a --efforts off,low

`--efforts` runs the same model at several reasoning levels, which is the
other half of the question: whether `director: low` is buying anything or is
pure latency on a role whose payload has already done the reasoning.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def build_payload(chat_id, db):
    """A director_interpret payload the size the Director really receives."""
    scene_row = db.q("SELECT value FROM world WHERE chat_id=? AND key LIKE ?",
                     (chat_id, "%scene%"), one=True)
    scene = json.loads(scene_row["value"]) if scene_row else {}
    cast = []
    for row in db.q("SELECT cc.char_id, ch.name, ch.sheet FROM chat_chars cc "
                    "JOIN characters ch ON ch.id = cc.char_id "
                    "WHERE cc.chat_id=?", (chat_id,)):
        try:
            sheet = json.loads(row["sheet"] or "{}")
        except (TypeError, ValueError):
            sheet = {}
        cast.append({
            "id": row["char_id"], "name": row["name"],
            "room": (scene.get("positions") or {}).get(row["name"]),
            # The Director really does receive a psychology digest per cast
            # member; omitting it would shrink the payload below life size.
            "psychology": (sheet.get("psychology") or {}).get("drive") or {},
            "traits": [t.get("name") for t in
                       ((sheet.get("psychology") or {}).get("traits") or [])
                       if isinstance(t, dict)][:6],
        })
    recent = []
    for row in db.q("SELECT id, idx, player_input FROM turns WHERE chat_id=? "
                    "ORDER BY idx DESC LIMIT 6", (chat_id,)):
        narr = db.q("SELECT v.content FROM variants v JOIN steps s "
                    "ON s.id = v.step_id WHERE s.turn_id=? AND s.key='narrator' "
                    "AND v.active=1", (row["id"],), one=True)
        prose = ""
        if narr:
            try:
                prose = json.loads(narr["content"]).get("prose") or ""
            except (TypeError, ValueError):
                pass
        recent.append({"idx": row["idx"],
                       "player_input": row["player_input"] or "",
                       "narration": prose})
    recent.reverse()
    return {
        "player_input": "\"We should go before it gets any later,\" you say, "
                        "standing.",
        "player_name": "Sarah Chen",
        "scene": scene,
        "cast": cast,
        "recent_turns": recent,
        "variant_seed": "shootout",
    }


def _post(prov, model, system, user, effort, timeout, max_tokens):
    import providers
    body = {"model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.5, "max_tokens": max_tokens}
    if effort:
        # The same two spellings providers.py sends, so this measures what the
        # engine would actually do rather than an approximation of it.
        body["reasoning_effort"] = effort
        body["reasoning"] = {"effort": effort}
    t0 = time.perf_counter()
    r = providers._session().post(
        prov["base_url"].rstrip("/") + "/chat/completions",
        headers=providers._headers(prov), json=body, timeout=timeout)
    dt = time.perf_counter() - t0
    if r.status_code >= 400:
        return None, dt, None, f"HTTP {r.status_code} {(r.text or '')[:90]}"
    data = r.json()
    text = (((data.get("choices") or [{}])[0].get("message") or {})
            .get("content") or "")
    usage = data.get("usage") or {}
    return text, dt, usage, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--provider", type=int, default=1)
    ap.add_argument("--chat", type=int, required=True)
    ap.add_argument("--models", required=True)
    ap.add_argument("--efforts", default="",
                    help="comma-separated reasoning levels, e.g. off,low")
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--max-tokens", type=int, default=12000)
    args = ap.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    import db
    db.configure(args.db)
    import llm_quality
    import prompts
    import schemas

    prov = dict(db.q("SELECT * FROM providers WHERE id=?",
                     (args.provider,), one=True))
    system = prompts.DEFAULT_PROMPTS["director_interpret"]
    payload = build_payload(args.chat, db)
    blob = json.dumps(payload, ensure_ascii=False)
    print(f"chat {args.chat}: payload {len(blob):,} chars "
          f"(~{len(blob)//4:,} tokens) + system ~{len(system)//4:,} tokens "
          f"= ~{(len(blob)+len(system))//4:,} total\n")

    efforts = [e.strip() for e in args.efforts.split(",") if e.strip()] or [""]
    rows = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        for effort in efforts:
            label = f"{model}  [{effort or 'unset'}]"
            print(f"  {label}", flush=True)
            times, passes, out_toks, errs = [], 0, [], []
            for _ in range(args.trials):
                text, dt, usage, err = _post(prov, model, system, blob, effort,
                                             args.timeout, args.max_tokens)
                times.append(dt)
                if err:
                    errs.append(err)
                    continue
                out_toks.append((usage or {}).get("completion_tokens") or 0)
                try:
                    parsed = llm_quality.strict_json_parse(text)
                except Exception as exc:
                    errs.append(f"parse: {str(exc)[:70]}")
                    continue
                report = schemas.validate_llm_output_strict(
                    "director_interpret", parsed, source_payload=payload)
                if report.valid:
                    passes += 1
                else:
                    errs.append("; ".join(report.errors[:2])[:100])
            med = statistics.median(times) if times else 0
            rows.append({"label": label, "med": med, "passes": passes,
                         "trials": args.trials,
                         "out": int(statistics.median(out_toks)) if out_toks else 0,
                         "errs": errs[:2]})
            mark = "PASS" if passes == args.trials else ("part" if passes else "FAIL")
            print(f"      {mark}  {passes}/{args.trials}  {med:.1f}s  "
                  f"{rows[-1]['out']} out tok", flush=True)
            for e in errs[:2]:
                print(f"        ! {e}", flush=True)

    print("\n=== fastest director on a REAL payload ===")
    rows.sort(key=lambda r: (r["passes"] < r["trials"], r["med"]))
    for r in rows:
        flag = "" if r["passes"] == r["trials"] else f"   ({r['passes']}/{r['trials']})"
        print(f"  {r['med']:>7.1f}s   {r['out']:>6} out tok   {r['label']}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
