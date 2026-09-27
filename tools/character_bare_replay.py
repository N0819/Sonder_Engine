"""Replay captured character calls under the full card and the bare card.

    python tools/character_bare_replay.py --db COPY.db [--db COPY2.db ...] \
        --beats N --out DIR [--arms both|bare|full] \
        [--layout system|sheet_first|sectioned] [--feelings]

On COPIES of story databases (the replay writes llm call records into the
database it runs on): for each sampled `character_major` capture, the call's
system prompt and payload are rebuilt from `llm_capture`/`llm_blobs`, and the
story's own character model (its `agent_models`) is asked once per arm -- the
full card exactly as captured, and the bare card with the gated sections the
payload calls for, read back by the decision model and compiled exactly as
`agents/character.py` does (`agents/character_bare.py`). Writes
`replay.jsonl` (per beat: the situation, both replies, the compiled bare
beat, timings, usage and the bare call's reasoning) and `side_by_side.md` for
reading. A beat whose arm fails is recorded with its error; the run goes on.

`--layout sheet_first` sends the bare call as the character sheet (system),
then what the character remembers and holds, then what is happening now, then
the card, last; `--layout sectioned` keeps the card as the system message and
sends the sheet, the memories and the moment in that order; `--feelings`
gives each beat the engine's own feelings block, which the captures predate.

Costs real money: one character call per beat per arm on the story's route,
plus the decision model's questions. Check the route's credit first.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


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


#: How much of each beat's reasoning the record keeps, so a slow beat can be
#: read for what it deliberated over (round four's slow half reasoned 13-27k
#: characters and nothing kept the text).
REASONING_KEPT = 40000


def _timed(fn, *args, **kwargs):
    t0 = time.time()
    out = fn(*args, **kwargs)
    return out, round(time.time() - t0, 2)


#: THE SHEET-FIRST LAYOUT (the owner, 2026-09-27: "(Character sheet)
#: (Memories) (current event) (Character prompt)", and "Situations should
#: include current mood of course"). Who the character is -- unchanged beat to
#: beat, so a cacheable prefix -- then what it remembers and holds, then what
#: is happening now with how it feels, then the card, nearest the reply.
SHEET_SELF_KEYS = ("name", "entity_id", "public_history", "psychology", "voice", "stance", "curiosity",
                   "abilities", "embodiment_capabilities", "sense_profile", "senses", "former_drives",
                   "former_projects")
#: What the character carries into the moment, OLDEST TO NEWEST so the
#: section runs into the present (the owner, 2026-09-27: notes and mind
#: models before perception): what it remembers and knows, then the people
#: it has readings of, then what it believes and is after, then what it said
#: and did lately, and last its previous choice and its own notes.
MEMORY_KEYS = ("memory", "private_knowledge", "world_knowledge", "relationships", "mind_models",
               "active_hypotheses")
HELD_SELF_KEYS = ("learned_beliefs", "learned_associations", "projects", "intentions", "steering_intention_ids",
                  "recent_self_lines", "recent_self_moves", "recent_self_refrain", "recent_tells",
                  "tell_grounds", "decision_continuity", "my_notes")


def _sections(payload):
    own = dict(payload.get("self") or {})
    sheet = {"self": {k: own[k] for k in SHEET_SELF_KEYS if k in own}}
    memories = {k: payload[k] for k in MEMORY_KEYS if k in payload}
    held = {k: own[k] for k in HELD_SELF_KEYS if k in own}
    if held:
        memories["self"] = held
    now_self = {k: v for k, v in own.items() if k not in SHEET_SELF_KEYS and k not in HELD_SELF_KEYS}
    now = {"self": now_self, **{k: v for k, v in payload.items() if k not in MEMORY_KEYS and k != "self"}}
    return sheet, memories, now


def _dump(value):
    return json.dumps(value, ensure_ascii=False)


def _sheet_first(payload, prompt):
    sheet, memories, now = _sections(payload)
    system = "WHO YOU ARE -- your character sheet:\n" + _dump(sheet)
    user = ("WHAT YOU REMEMBER AND HOLD:\n" + _dump(memories)
            + "\n\nWHAT IS HAPPENING NOW:\n" + _dump(now) + "\n\n" + prompt)
    return system, user


def _sectioned(payload, prompt):
    """The owner's order in the user message -- sheet, memories, the moment
    with its mood -- with the card staying the system message. Round five
    found the sheet-first layout read better (two blind judges, 12 of 17
    agreed beats) and ran past its turn and put inner states into acts twice
    as often; this separates the order from the card's place."""
    sheet, memories, now = _sections(payload)
    user = ("WHO YOU ARE -- your character sheet:\n" + _dump(sheet)
            + "\n\nWHAT YOU REMEMBER AND HOLD:\n" + _dump(memories)
            + "\n\nWHAT IS HAPPENING NOW:\n" + _dump(now))
    return prompt, user


def _ask_layout(layout, payload, prompt, temperature):
    """One call in a rearranged layout, validated as the engine validates a
    bare reply (no repair: a failure is recorded, not retried)."""
    from llm.llm_quality import _step_json_schema, strict_json_parse
    from llm.providers import chat_complete
    from llm.schemas import validate_llm_output_strict
    system, user = (_sheet_first if layout == "sheet_first" else _sectioned)(payload, prompt)
    raw = chat_complete("character_major", system, user, temperature=temperature,
                        json_schema=_step_json_schema("character_bare"))
    report = validate_llm_output_strict("character_bare", strict_json_parse(raw))
    if not report.valid:
        raise ValueError(f"{layout} reply failed validation: {report.errors[:3]}")
    return report.output


def _feelings(name, sheet, payload):
    """How this mind feels now, by the engine's own affect pass over its own
    payload -- the captures predate the given-feelings block."""
    from mind import affect_pass
    own = payload.get("self") or {}
    active = own.get("active_state") or {}
    affect = active.get("affect") if isinstance(active.get("affect"), dict) else {}
    felt = affect_pass.before_call(name, sheet, active, affect.get("baseline"), 1.0,
                                   observations=_observations(payload),
                                   memory_context=payload.get("memory") or {},
                                   relationships=payload.get("relationships") or {}, language="en")
    return affect_pass.feelings_block(felt)


def _bare_arm(name, sheet, payload, own, layout, feelings):
    """One beat under the bare card: the decision model before, the call in
    the chosen layout, the decision model after, compiled as the engine
    compiles it."""
    from agents import character_bare
    from agents.character import character_temperature
    from agents.common import _agent_json
    from llm import providers
    from mind import character_jev as jev
    from mind.affect_appraisal import _probabilities

    h = character_bare.holding_from(
        name, sheet, payload, _observations(payload), payload.get("memory") or {},
        (own.get("active_state") or {}), language="en")
    before, before_s = _timed(jev.ask, jev.state_text(h), jev.before_questions(h))
    disputed = jev.read_before(before, h)
    dispute_shares = [round(_probabilities(before.get(f"dispute:{i}")).get("yes", 0.0), 3)
                      for i in range(len(h.memories))] if before else []
    bare_payload = dict(payload)
    if feelings:
        bare_payload["self"] = {**(payload.get("self") or {}), "feelings": _feelings(name, sheet, payload)}
    if disputed:
        bare_payload["memory"] = {**(payload.get("memory") or {}),
                                  "may_mean_otherwise": [m["text"] for m in disputed]}
    modules = character_bare.modules_for(bare_payload, disputed=disputed)
    prompt = character_bare.prompt(name, modules, "en")
    if layout in ("sheet_first", "sectioned"):
        raw, call_s = _timed(_ask_layout, layout, bare_payload, prompt, character_temperature(sheet))
    else:
        raw, call_s = _timed(_agent_json, "character_major", "character_bare", prompt, bare_payload,
                             temperature=character_temperature(sheet))
    h.reasoning = str(providers.last_reasoning.get() or "")
    questions = jev.after_questions(h, raw)
    answers, after_s = _timed(jev.ask, jev.state_text(h, raw), questions)
    compiled, warnings = character_bare.compile_bare(raw, answers, h)
    return {"reply": raw, "compiled": compiled, "warnings": warnings,
            "modules": modules, "disputed": [m["text"] for m in disputed],
            "dispute_shares": dispute_shares,
            "seconds": call_s, "jev_before_s": before_s, "jev_after_s": after_s,
            "questions": len(questions), "reasoning_chars": len(h.reasoning),
            "reasoning": h.reasoning[:REASONING_KEPT],
            "prompt_chars": len(prompt), "layout": layout,
            "feelings": (bare_payload.get("self") or {}).get("feelings")}


def replay(db_path, beats, arms, layout="system", feelings=False):
    from core import db
    db.configure(str(db_path))
    from agents.character import character_temperature
    from agents.common import _agent_json
    from llm import providers

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
                try:
                    reply, seconds = _timed(_agent_json, "character_major", "character_kernel", system, payload,
                                            temperature=character_temperature(sheet))
                    record["full"] = {"reply": reply, "seconds": seconds, "calls": list(ledger)}
                except Exception as exc:  # noqa: BLE001 -- one failed beat is a finding, not the run's end
                    record["full"] = {"error": f"{type(exc).__name__}: {str(exc)[:300]}", "seconds": None,
                                      "calls": list(ledger)}
                ledger.clear()
            if arms in ("both", "bare"):
                try:
                    record["bare"] = _bare_arm(name, sheet, payload, own, layout, feelings)
                except Exception as exc:  # noqa: BLE001 -- one failed beat is a finding, not the run's end
                    record["bare"] = {"error": f"{type(exc).__name__}: {str(exc)[:300]}", "seconds": None,
                                      "layout": layout}
                record["bare"]["calls"] = list(ledger)
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
    # The compiled sequence holds the reply's NON-EMPTY steps, in order (an
    # element carrying none of say/do/ponder is skipped), so pair with those.
    steps = [s for s in reply.get("sequence") or []
             if isinstance(s, dict) and any(str(s.get(k) or "").strip() for k in ("say", "do", "ponder"))]
    for s, typed in zip(steps, (compiled or {}).get("sequence") or []):
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
        if "full" in r and "error" in r["full"]:
            md.append(f"**Full card**: failed -- {r['full']['error']}\n")
        elif "full" in r:
            md.append(f"**Full card** ({r['full']['seconds']} s):\n\n{_conduct_full(r['full']['reply'])}\n")
        if "bare" in r and "error" in r["bare"]:
            md.append(f"**Bare card**: failed -- {r['bare']['error']}\n")
        elif "bare" in r:
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
    ap.add_argument("--layout", choices=("system", "sheet_first", "sectioned"), default="system",
                    help="system: the card as the system message, the payload as the user message; "
                         "sheet_first: the sheet, then memories, then what is happening now, then the card; "
                         "sectioned: the card as the system message, then the sheet, memories and now")
    ap.add_argument("--feelings", action="store_true",
                    help="give each beat its feelings by the engine's affect pass (the captures predate it)")
    args = ap.parse_args()
    records = []
    for path in args.db:
        records += replay(path, args.beats, args.arms, layout=args.layout, feelings=args.feelings)
    write(records, Path(args.out))
    print(f"wrote {len(records)} beats to {args.out}")


if __name__ == "__main__":
    main()
