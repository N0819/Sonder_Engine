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
                  "tell_grounds", "decision_continuity", "notebook", "my_notes")


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


#: How many times a rearranged layout's request is sent when its reply does
#: not validate, or whose provider returns nothing -- the engine's own path
#: would repair it; this stands in. Three since round nine (2026-09-27): GLM
#: thinking on NanoGPT ended after its reasoning with no answer, or went
#: silent, on 10 of 16 re-sends of one of Margit's prompts, whatever the card.
LAYOUT_ATTEMPTS = 3


def _ask_layout(layout, payload, prompt, temperature):
    """One call in a rearranged layout, validated as the engine validates a
    bare reply; a reply that does not validate, or a provider that returns
    nothing, is asked again (the engine's path repairs), and a last failure
    is recorded."""
    from llm.llm_quality import _step_json_schema, strict_json_parse
    from llm.providers import LLMError, chat_complete
    from llm.schemas import validate_llm_output_strict
    system, user = (_sheet_first if layout == "sheet_first" else _sectioned)(payload, prompt)
    errors = []
    for _attempt in range(LAYOUT_ATTEMPTS):
        try:
            raw = chat_complete("character_major", system, user, temperature=temperature,
                                json_schema=_step_json_schema("character_bare"))
        except LLMError as exc:  # a silent provider is a failed attempt like an empty answer
            errors.append(f"{type(exc).__name__}: {str(exc)[:160]}")
            continue
        try:
            report = validate_llm_output_strict("character_bare", strict_json_parse(raw))
        except Exception as exc:  # noqa: BLE001 -- unparseable is a failed attempt like any other
            errors.append(f"{type(exc).__name__}: {str(exc)[:160]} -- reply began {str(raw)[:160]!r}")
            continue
        if report.valid:
            return report.output
        errors.append(f"{report.errors[:3]} -- reply began {str(raw)[:160]!r}")
    raise ValueError(f"{layout} reply failed validation {len(errors)} times: {errors}")


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


#: The turn the replay's rebuilt notebook stands at: every held note is as
#: fresh as the capture showed it (no fade between capture and replay).
REPLAY_TURN = 1000


def _stored_from_capture(payload):
    """A stored state for the notebook, rebuilt from what the capture's
    payload showed of it: the leading and competing readings per subject and
    kind (`mind_models`, as `mind_models_for_payload` rendered them). The
    captures predate the notebook; the reminders it keeps start empty."""
    models = {}
    for about, kinds in (payload.get("mind_models") or {}).items():
        hyps = []
        for kind, block in (kinds or {}).items():
            for entry in [(block or {}).get("leading"), *((block or {}).get("competitors") or [])]:
                if isinstance(entry, dict) and str(entry.get("claim") or "").strip():
                    hyps.append({"about_entity": about, "kind": kind, "claim": entry["claim"],
                                 "confidence": float(entry.get("confidence") or 0.5),
                                 "last_updated_turn": REPLAY_TURN, "first_seen_turn": REPLAY_TURN})
        if hyps:
            models[about] = {"hypotheses": hyps}
    return {"mind_models": models}


def _bare_arm(name, sheet, payload, own, layout, feelings, notebook=False, stored=None, turn=None):
    """One beat under the bare card: the decision model before, the call in
    the chosen layout, the decision model after, compiled as the engine
    compiles it. `notebook`: the call shows the notebook (mind/notebook.py)
    in place of the renderings it replaces, as the engine's bare path does --
    rebuilt from the capture, or, in a chain, the character's own (`stored`,
    at `turn`)."""
    from agents import character_bare
    from agents.character import character_temperature
    from agents.common import _agent_json
    from llm import providers
    from mind import character_jev as jev
    from mind.affect_appraisal import _probabilities

    view = None
    if notebook:
        view = character_bare.notebook_for(
            stored if stored is not None else _stored_from_capture(payload), payload, _observations(payload),
            name, turn if turn is not None else REPLAY_TURN)
    h = character_bare.holding_from(
        name, sheet, payload, _observations(payload), payload.get("memory") or {},
        (own.get("active_state") or {}), language="en", notebook_view=view)
    before, before_s = _timed(jev.ask_before, h)
    disputed = jev.read_before(before, h)
    dispute_shares = [round(_probabilities(before.get(f"dispute:{i}")).get("yes", 0.0), 3)
                      for i in range(len(h.memories))] if before else []
    bare_payload = dict(payload)
    if feelings:
        bare_payload["self"] = {**(payload.get("self") or {}), "feelings": _feelings(name, sheet, payload)}
    if disputed:
        bare_payload["memory"] = {**(payload.get("memory") or {}),
                                  "may_mean_otherwise": [m["text"] for m in disputed]}
    if notebook:
        bare_payload = character_bare.with_notebook(bare_payload, view)
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
    # As the engine does: the note check asked before the call is read with
    # the rest.
    compiled, warnings = character_bare.compile_bare(raw, {**(before or {}), **answers}, h)
    held_checks = [{"id": row.get("id"), "about": row.get("about"), "note": str(row.get("note") or "")[:200],
                    "shares": {k: round(v, 3) for k, v in
                               _probabilities((before or {}).get(f"held:{k_}:touched")).items()},
                    "now": jev.pick(before or {}, f"held:{k_}:now")}
                   for k_, row in enumerate(jev.notes_in_play(h))]
    return {"reply": raw, "compiled": compiled, "warnings": warnings,
            "modules": modules, "disputed": [m["text"] for m in disputed],
            "dispute_shares": dispute_shares, "held_checks": held_checks,
            "seconds": call_s, "jev_before_s": before_s, "jev_after_s": after_s,
            "questions": len(questions), "reasoning_chars": len(h.reasoning),
            "reasoning": h.reasoning[:REASONING_KEPT],
            "prompt_chars": len(prompt), "layout": layout,
            "feelings": (bare_payload.get("self") or {}).get("feelings"),
            **({"notebook_shown": view, "payload_chars": len(_dump(bare_payload))} if notebook else {})}


def chain(db_path, name, layout="sectioned", feelings=True, limit=None):
    """ONE CHARACTER'S CAPTURES IN ORDER, ITS NOTEBOOK CARRIED FORWARD: the
    story's captured moments reach the mind as they did, and what it keeps --
    its notes about people and things, its concerns, its projects, its
    reminders, its running notes and the recall it asked for -- is its own,
    each beat's compiled output applied the way commit applies it
    (`theory_of_mind.apply_mind_model_updates` after the kind caps,
    `notebook.apply_notebook_ops`, the concerns the beat left,
    `affect.apply_project_ops`). The first capture's readings seed it."""
    from core import db
    db.configure(str(db_path))
    from llm import providers
    from mind import affect
    from mind import notebook as nb
    from mind import theory_of_mind as tom

    rows = db.q("SELECT id, turn_id, payload_hashes FROM llm_capture WHERE role='character_major' AND ok=1 "
                "ORDER BY id")
    sheet = _sheet(db, name)
    state, out = None, []
    for cap in rows:
        if "original_request" in (cap["payload_hashes"] or ""):
            continue
        payload = _payload(db, cap["payload_hashes"])
        own = dict(payload.get("self") or {})
        if str(own.get("name") or "") != name:
            continue
        if limit is not None and len(out) >= limit:
            break
        turn_row = db.q("SELECT idx FROM turns WHERE id=?", (cap["turn_id"],), one=True)
        turn_idx = int(turn_row["idx"]) if turn_row else len(out)
        if state is None:
            state = _stored_from_capture(payload)
            for hyps in (m["hypotheses"] for m in state["mind_models"].values()):
                for h in hyps:
                    h["last_updated_turn"] = h["first_seen_turn"] = turn_idx
            state["active_concerns"] = list((own.get("active_state") or {}).get("active_concerns") or [])
            state["projects"] = [p for p in own.get("projects") or [] if isinstance(p, dict)]
            state["former_projects"] = []
            state["my_notes"] = []
        # The chain's own keeping, in place of the capture's.
        active = dict(own.get("active_state") or {})
        active["active_concerns"] = list(state["active_concerns"])
        own["active_state"] = active
        own["projects"] = list(state["projects"])
        if state["my_notes"]:
            own["my_notes"] = list(state["my_notes"])
        chained = {**payload, "self": own}
        ledger = []
        token = providers.call_ledger_sink.set(ledger.append)
        try:
            b = _bare_arm(name, sheet, chained, own, layout, feelings, notebook=True, stored=state,
                          turn=turn_idx)
        except Exception as exc:  # noqa: BLE001 -- one failed beat is a finding; the chain goes on
            b = {"error": f"{type(exc).__name__}: {str(exc)[:300]}", "seconds": None}
        finally:
            providers.call_ledger_sink.reset(token)
        b["calls"] = list(ledger)
        record = {"db": Path(db_path).name, "capture": cap["id"], "turn_id": cap["turn_id"], "turn": turn_idx,
                  "name": name,
                  "situation": [str((r.get("observed") or {}).get("text") or "")[:300]
                                for r in (payload.get("perception") or {}).get("events") or []
                                if isinstance(r, dict)],
                  "bare": b}
        if "error" not in b:
            compiled = b["compiled"] or {}
            state = tom.apply_mind_model_updates(
                state, tom.cap_mind_model_updates(compiled.get("mind_model_updates") or []), turn_idx)
            state = nb.apply_notebook_ops(state, compiled.get("notebook_ops") or [], turn_idx)
            state["active_concerns"] = list((compiled.get("active_state") or {}).get("active_concerns") or [])
            projects, former, project_warnings = affect.apply_project_ops(
                state["projects"], state["former_projects"], compiled.get("project_ops") or [], turn_idx)
            state["projects"], state["former_projects"] = projects, former
            note = " ".join(str(compiled.get("note") or "").split())
            if note:
                state["my_notes"] = (state["my_notes"] + [{"turn": turn_idx, "note": note[:300]}])[-5:]
            ponder = compiled.get("ponder")
            if isinstance(ponder, dict) and ponder.get("query"):
                state["memory_ponder"] = {"query": ponder["query"], "set_turn": turn_idx}
            record["chain"] = {
                "notes": sum(len(m.get("hypotheses") or []) for m in state.get("mind_models", {}).values()),
                "subjects": len(state.get("mind_models") or {}), "reminders": len(state.get("notebook") or []),
                "concerns": len(state["active_concerns"]), "projects": [p.get("project") for p in projects],
                "project_warnings": project_warnings}
        out.append(record)
        chain_line = record.get("chain") or {}
        print(f"{record['db']} {name} capture {cap['id']} turn {turn_idx}: {b.get('seconds')}s; "
              f"notes {chain_line.get('notes')} reminders {chain_line.get('reminders')} "
              f"concerns {chain_line.get('concerns')} projects {chain_line.get('projects')}"
              + (f"; FAILED {b['error'][:300]}" if "error" in b else ""), flush=True)
    return out


def replay(db_path, beats, arms, layout="system", feelings=False, notebook=False):
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
                    record["bare"] = _bare_arm(name, sheet, payload, own, layout, feelings, notebook=notebook)
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
    ap.add_argument("--notebook", action="store_true",
                    help="show the notebook (mind/notebook.py), rebuilt from what each capture held, in place "
                         "of mind_models, active_hypotheses, projects and concerns -- as the engine's bare path does")
    ap.add_argument("--feelings", action="store_true",
                    help="give each beat its feelings by the engine's affect pass (the captures predate it)")
    ap.add_argument("--chain", metavar="NAME",
                    help="replay every capture of the character NAME in order, its notebook carried forward "
                         "(the first --db only; --beats caps how many)")
    args = ap.parse_args()
    if args.chain:
        records = chain(args.db[0], args.chain, layout=args.layout, feelings=args.feelings,
                        limit=args.beats if args.beats and args.beats > 2 else None)
        write_chain(records, Path(args.out))
        print(f"wrote {len(records)} chained beats to {args.out}")
        return
    records = []
    for path in args.db:
        records += replay(path, args.beats, args.arms, layout=args.layout, feelings=args.feelings,
                          notebook=args.notebook)
    write(records, Path(args.out))
    print(f"wrote {len(records)} beats to {args.out}")


def write_chain(records, out_dir):
    """`replay.jsonl`, and `chain.md`: per beat, what reached the mind, what
    it did, its notebook as shown, what it wrote there and where that landed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "replay.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    md = [f"# {records[0]['name'] if records else ''}: the notebook carried through the story\n"]
    for r in records:
        b = r["bare"]
        md.append(f"## turn {r['turn']} (capture {r['capture']})\n")
        md.append("\n".join(f"> {s}" for s in r["situation"][:4]) + "\n")
        if "error" in b:
            md.append(f"FAILED: {b['error']}\n")
            continue
        for s in b["reply"].get("sequence") or []:
            for k in ("say", "do", "ponder"):
                if str(s.get(k) or "").strip():
                    md.append(f"- {k}: {s[k]}")
        shown = b.get("notebook_shown") or {}
        md.append("\nShown:")
        for section, rows in shown.items():
            for e in rows:
                about = f"{e['about']}: " if e.get("about") else ""
                md.append(f"- [{section} {e['id']}] {about}{e.get('note', '')}"
                          + (f" ({e['sure']})" if e.get("sure") else "")
                          + (f" (until: {e['until']})" if e.get("until") else ""))
        md.append("\nWrote:")
        for e in b["reply"].get("notebook") or []:
            md.append("- " + json.dumps({k: v for k, v in e.items() if v}, ensure_ascii=False))
        compiled = b.get("compiled") or {}
        md.append("\nLanded:")
        for u in compiled.get("mind_model_updates") or []:
            md.append(f"- {u.get('op') or 'add'} [{u.get('kind')}] {u.get('about_entity')}: "
                      f"{str(u.get('claim'))[:200]} ({u.get('confidence')})")
        for op in compiled.get("notebook_ops") or []:
            md.append(f"- reminder {op['op']} {op.get('id', '')} {op.get('note', '')}")
        for op in compiled.get("project_ops") or []:
            md.append(f"- project {json.dumps(op, ensure_ascii=False)}")
        md.append(f"\nKept after: {json.dumps(r.get('chain') or {}, ensure_ascii=False)}\n")
    (out_dir / "chain.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
