"""Replay captured character calls under the full card and the bare card.

    python tools/character_bare_replay.py --db COPY.db [--db COPY2.db ...] \
        --beats N --out DIR [--arms both|bare|full]

On COPIES of story databases (the replay writes llm call records into the
database it runs on): for each sampled `character_major` capture, the call's
system prompt and payload are rebuilt from `llm_capture`/`llm_blobs`, and the
story's own character model (its `agent_models`) is asked once per arm -- the
full card exactly as captured, and the bare card with the gated sections the
payload calls for, read back by the decision model and compiled exactly as
`agents/character.py` does (`agents/character_bare.py`). Writes
`replay.jsonl` (per beat: the situation, both replies, the compiled bare
beat, timings and usage) and `side_by_side.md` for reading.

Costs real money: one character call per beat per arm on the story's route,
plus the decision model's questions. Check the route's credit first.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _blob(db, digest):
    row = db.q("SELECT body FROM llm_blobs WHERE hash=?", (digest,), one=True)
    return row["body"] if row else None


def _payload(db, hashes):
    out = {}
    for key, digest in (json.loads(hashes or "{}") or {}).items():
        body = _blob(db, digest)
        try:
            out[key] = json.loads(body) if body is not None else None
        except (TypeError, ValueError):
            out[key] = body
    return out


def _sample(db, beats):
    rows = db.q("SELECT id, turn_id, system_hash, payload_hashes, response_hash, reasoning_hash, "
                "duration FROM llm_capture WHERE role='character_major' AND ok=1 ORDER BY id")
    rows = [r for r in rows if "original_request" not in (r["payload_hashes"] or "")]
    if len(rows) <= beats:
        return rows
    step = len(rows) / float(beats)
    return [rows[int(i * step)] for i in range(beats)]


def _observations(payload):
    perception = payload.get("perception") or {}
    rows = []
    for key in ("events", "changes_noticed", "current_state"):
        for row in perception.get(key) or []:
            if isinstance(row, dict):
                rows.append({**row, "standing": key == "current_state" or row.get("standing")})
    return rows


def _sheet(db, name):
    row = db.q("SELECT sheet FROM characters WHERE name=?", (name,), one=True)
    return json.loads(row["sheet"]) if row and row["sheet"] else {}


def _timed(fn, *args, **kwargs):
    t0 = time.time()
    out = fn(*args, **kwargs)
    return out, round(time.time() - t0, 2)


def replay(db_path, beats, arms):
    from core import db
    db.configure(str(db_path))
    from agents import character_bare
    from agents.character import character_temperature
    from agents.common import _agent_json
    from llm import providers
    from mind import character_jev as jev

    out = []
    for cap in _sample(db, beats):
        payload = _payload(db, cap["payload_hashes"])
        system = _blob(db, cap["system_hash"]) or ""
        own = (payload.get("self") or {})
        name = str(own.get("name") or "")
        sheet = _sheet(db, name)
        record = {"db": Path(db_path).name, "capture": cap["id"], "turn_id": cap["turn_id"], "name": name,
                  "situation": [str((r.get("observed") or {}).get("text") or "")[:300]
                                for r in (payload.get("perception") or {}).get("events") or []
                                if isinstance(r, dict)]}
        ledger = []
        token = providers.call_ledger_sink.set(ledger.append)
        try:
            if arms in ("both", "full"):
                reply, seconds = _timed(_agent_json, "character_major", "character_kernel", system, payload,
                                        temperature=character_temperature(sheet))
                record["full"] = {"reply": reply, "seconds": seconds, "calls": list(ledger)}
                ledger.clear()
            if arms in ("both", "bare"):
                h = character_bare.holding_from(
                    name, sheet, payload, _observations(payload), payload.get("memory") or {},
                    (own.get("active_state") or {}), language="en")
                disputed, before_s = _timed(lambda: jev.read_before(
                    jev.ask(jev.state_text(h), jev.before_questions(h)), h))
                bare_payload = dict(payload)
                if disputed:
                    bare_payload["memory"] = {**(payload.get("memory") or {}),
                                              "may_mean_otherwise": [m["text"] for m in disputed]}
                modules = character_bare.modules_for(bare_payload, disputed=disputed)
                prompt = character_bare.prompt(name, modules, "en")
                raw, call_s = _timed(_agent_json, "character_major", "character_bare", prompt, bare_payload,
                                     temperature=character_temperature(sheet))
                h.reasoning = str(providers.last_reasoning.get() or "")
                questions = jev.after_questions(h, raw)
                answers, after_s = _timed(jev.ask, jev.state_text(h, raw), questions)
                compiled, warnings = character_bare.compile_bare(raw, answers, h)
                record["bare"] = {"reply": raw, "compiled": compiled, "warnings": warnings,
                                  "modules": modules, "disputed": [m["text"] for m in disputed],
                                  "seconds": call_s, "jev_before_s": before_s, "jev_after_s": after_s,
                                  "questions": len(questions), "reasoning_chars": len(h.reasoning),
                                  "prompt_chars": len(prompt), "calls": list(ledger)}
        finally:
            providers.call_ledger_sink.reset(token)
        out.append(record)
        print(f"{record['db']} capture {cap['id']} {name}: "
              + ", ".join(f"{arm} {record[arm]['seconds']}s" for arm in ("full", "bare") if arm in record),
              flush=True)
    return out


def _conduct_full(reply):
    lines = []
    for s in (reply or {}).get("sequence") or []:
        if not isinstance(s, dict):
            continue
        if s.get("type") == "speech":
            lines.append(f'- says ({s.get("volume") or "normal"}): "{s.get("text")}"')
        elif s.get("type") == "action":
            lines.append(f"- does: {s.get('attempt') or s.get('observable')}")
        elif s.get("type") == "ponder":
            lines.append(f"- ponders: {s.get('query')}")
    decision = ((reply or {}).get("state") or {}).get("decision") or {}
    if decision.get("hinge"):
        lines.append(f"- hinge: {decision['hinge']}")
    return "\n".join(lines) or "- (nothing)"


def _conduct_bare(reply, compiled):
    lines = []
    for s, typed in zip(reply.get("sequence") or [], (compiled or {}).get("sequence") or []):
        why = f" -- why: {s.get('why')}" if s.get("why") else ""
        if s.get("say"):
            hidden = f", hidden from {', '.join(typed.get('conceal_from') or [])}" if typed.get("conceal_from") else ""
            lines.append(f'- says ({typed.get("volume")}, to {", ".join(typed.get("targets") or []) or "no one named"}'
                         f'{hidden}): "{s["say"]}"{why}')
        elif s.get("do"):
            seen = "" if typed.get("observable") else " [unseen]"
            lines.append(f"- does{seen}: {s['do']}{why}")
        elif s.get("ponder"):
            lines.append(f"- ponders: {s['ponder']}{why}")
    for key in ("want", "held_back", "hinge", "unsure", "note"):
        if reply.get(key):
            lines.append(f"- {key}: {reply[key]}")
    for key in ("people", "changes"):
        for line in reply.get(key) or []:
            lines.append(f"- {key}: {line}")
    filed = {k: len(v) for k, v in (compiled or {}).items()
             if isinstance(v, list) and k.endswith(("_ops", "_updates", "_lines", "_disputes", "_effects")) and v}
    if filed:
        lines.append(f"- filed: {filed}")
    return "\n".join(lines) or "- (nothing)"


def write(records, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "replay.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    md = ["# Full card against bare card, same payloads\n"]
    for r in records:
        md.append(f"## {r['db']} -- capture {r['capture']} -- {r['name']}\n")
        md.append("What reached them:\n" + "\n".join(f"> {s}" for s in r["situation"][:6]) + "\n")
        if "full" in r:
            md.append(f"**Full card** ({r['full']['seconds']} s):\n\n{_conduct_full(r['full']['reply'])}\n")
        if "bare" in r:
            b = r["bare"]
            md.append(f"**Bare card** ({b['seconds']} s; decision model {b['jev_before_s']} s before, "
                      f"{b['jev_after_s']} s after, {b['questions']} questions; modules {b['modules'] or 'none'}):"
                      f"\n\n{_conduct_bare(b['reply'], b['compiled'])}\n")
    (out_dir / "side_by_side.md").write_text("\n".join(md), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", action="append", required=True, help="a COPY of a story database")
    ap.add_argument("--beats", type=int, default=2, help="captures sampled per database")
    ap.add_argument("--arms", choices=("both", "bare", "full"), default="both")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    records = []
    for path in args.db:
        records += replay(path, args.beats, args.arms)
    write(records, Path(args.out))
    print(f"wrote {len(records)} beats to {args.out}")


if __name__ == "__main__":
    main()
