#!/usr/bin/env python3
"""Exercise prose -> causal program -> world -> perception in private scratch DBs.

Live runs require an explicit configuration source; that source is opened
read-only and only its provider/settings rows are copied. No production story
is copied or committed. Every case owns a fresh database so case selection does
not change actor or event IDs. Scratch databases contain credentials and must
not be published. JSON/Markdown exports are checked against those credentials.

Replay uses accepted captured responses only, disables all provider rows and
blocks network connections. It never retries a missing response with a model.
Payload/prompt drift is recorded so replay is not mistaken for a fresh test.

Intermediate checks require a reviewed event-to-chrono alignment. The runner
does not guess semantic correspondence from prose or silently equate the
fixture's event numbering with model segmentation. Unaligned checks remain
unreviewed; final world/quote checks can run without alignment.

Examples::

    .venv/bin/python tools/causal_stress.py run --out /tmp/causal-live \
        --source-db engine.db --provider openrouter --model MODEL_NAME
    .venv/bin/python tools/causal_stress.py run --out /tmp/causal-replay \
        --replay-root /tmp/causal-live
    .venv/bin/python tools/causal_stress.py score --root /tmp/causal-live \
        --alignment /tmp/reviewed-alignment.json

Alignment format: {"case_id": {"event_id": {"stage": "interpret",
"chrono_id": 3}}}. A merged span may answer several adjacent expected events;
the reviewer must record only states actually observable at that boundary.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from threading import Lock
import time
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CORPUS = ROOT / "tests/data/causal_stress_holdout.json"
REPLAY_SETTINGS = ("ui_language", "director_fanout_mode", "director_orchestration",
                   "resolve_deep_audit", "attire_beneath")
WORLD_FIELDS = ("entities", "positions", "stations", "poses", "contacts",
                "contained", "attire", "substances", "rooms")


def fingerprint(value):
    """Order-independent hash of a JSON value, including prompts when given."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()


@contextmanager
def no_network():
    """Fail closed before any replay transport can connect or resolve DNS."""
    def refuse(*_args, **_kwargs):
        raise RuntimeError("Network is disabled during causal replay")
    with ExitStack() as stack:
        for target in ("socket.create_connection", "socket.getaddrinfo",
                       "socket.socket.connect", "socket.socket.connect_ex"):
            stack.enter_context(patch(target, refuse))
        yield


def load_cases(path, selected=()):
    """Load corpus cases, refusing unsafe paths and misspelled selections."""
    raw = json.loads(Path(path).read_text())
    cases = raw if isinstance(raw, list) else raw["cases"]
    seen = set()
    for case in cases:
        ident = case["id"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", ident) or ident in seen:
            raise ValueError("Case IDs must be unique safe directory names")
        seen.add(ident)
    unknown = set(selected) - seen
    if unknown:
        raise ValueError("Unknown case IDs: " + ", ".join(sorted(unknown)))
    return [case for case in cases if not selected or case["id"] in selected]


def save_artifact(path, value, database=None):
    """Export only text that contains none of the scratch configuration keys."""
    text = value if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False, indent=2, default=str)
    if database:
        from tools.export_bench import leaks
        if leaks(text, str(database)):
            raise RuntimeError("Refused an artifact containing a configured secret")
    Path(path).write_text(text)
    Path(path).chmod(0o600)


def prepare_database(target, source=None, captured_settings=None, provider=None,
                     model=None):
    """Create a fresh isolated DB; never reuse a story or a credential copy."""
    from core import db
    target = Path(target).resolve()
    if target.exists():
        raise ValueError("Scratch database already exists: " + str(target))
    if source and (not Path(source).is_file() or Path(source).resolve() == target):
        raise ValueError("Configuration source must be a different existing database")
    db.configure(str(target))
    db.init()
    target.chmod(0o600)
    if source:
        from tools.export_bench import copy_rows
        db.close_connection()
        copy_rows(str(Path(source).resolve()), str(target))
        db.configure(str(target))
        with db.transaction() as connection:
            connection.execute("UPDATE providers SET enabled=0 WHERE kind NOT IN ('openrouter','nanogpt')")
    else:
        # Replays need no credentials, even if a default installation has them.
        with db.transaction() as connection:
            connection.execute("UPDATE providers SET enabled=0")
        for key, value in (captured_settings or {}).items():
            if key in REPLAY_SETTINGS and value is not None:
                db.set_setting(key, value)
    if provider:
        row = db.q("SELECT id FROM providers WHERE kind=? AND enabled=1 ORDER BY id LIMIT 1",
                   (provider,), one=True)
        if not row:
            raise ValueError("No enabled provider of requested kind in configuration source")
        models = json.loads(db.get_setting("agent_models") or "{}")
        for role in ("default", "director", "director_spatial", "director_objects",
                     "director_body", "director_contact", "director_social"):
            models[role] = dict(models.get(role) or {}, provider=row["id"], model=model)
        db.set_setting("agent_models", json.dumps(models))
    for key, value in {"nsfw_enabled": "0", "backdrops_enabled": "0",
                       "ambience_enabled": "0", "llm_capture_enabled": "1",
                       "llm_capture_bodies": "full"}.items():
        db.set_setting(key, value)
    return target


def seed_case(case):
    """Create only the synthetic fixture and its single uncommitted input turn."""
    from core import db
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import default_character_data, default_persona_data
    from story.scene import set_player_authority
    name = case["primary_name"]
    now = time.time()
    persona = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                    (name, json.dumps(default_persona_data(name)), "{}"))
    cid = db.qi("INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
                ("Causal stress: " + case["id"], "", now, persona))
    names = [name]
    for index, person in enumerate(case.get("characters", [])):
        person = person["name"] if isinstance(person, dict) else person
        if person == name:
            continue
        names.append(person)
        char = db.qi("INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
                     (person, json.dumps(default_character_data(person)), "{}", now,
                      "causal_stress_" + case["id"] + "_" + str(index)))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
              (cid, char, "active", "{}"))
    db.wset(cid, "scene", deepcopy(case["scene"]))
    db.wset(cid, "known", {person: [other for other in names if person != other]
                           for person in names})
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0, "display": "afternoon"})
    set_player_authority(cid, case.get("authority_mode", "world_author"))
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, 1, case["prose"], now))
    return PipelineContext(chat=ChatData(cid, case["id"], persona, None, "", now),
                           turn=TurnData(tid, cid, 1, case["prose"], now),
                           cast=cast, input=case["prose"])


class CapturedReplies:
    """Return accepted replies in each role's original order, or fail closed."""

    def __init__(self, exchanges):
        self.exchanges = exchanges
        self.consumed = set()
        self.records = []
        self.failures = []
        self.lock = Lock()

    def __call__(self, role, step_key, system, payload, **_kwargs):
        from llm.llm_quality import strict_json_parse
        from llm.schemas import validate_llm_output_strict
        with self.lock:
            found = next(((index, exchange) for index, exchange in enumerate(self.exchanges)
                          if index not in self.consumed and exchange.get("ok")
                          and exchange.get("role") == role), None)
            if found is None:
                self.failures.append({"role": role, "step_key": step_key, "error": "missing accepted reply"})
                raise RuntimeError("No accepted captured reply for " + role + " " + step_key)
            index, exchange = found
            self.consumed.add(index)
            report = validate_llm_output_strict(
                step_key, strict_json_parse(exchange["response"]), source_payload=payload)
            record = {"index": index, "role": role, "step_key": step_key,
                      "payload_matches": fingerprint(exchange.get("payload")) == fingerprint(payload),
                      "system_matches": fingerprint(exchange.get("system")) == fingerprint(system),
                      "valid_under_current_contract": report.valid}
            self.records.append(record)
            if not report.valid:
                self.failures.append({"role": role, "step_key": step_key, "error": "reply invalid under current contract"})
                raise RuntimeError("Captured reply fails current contract: " + str(report.errors[:3]))
            return report.output

    def unused(self):
        return [i for i, exchange in enumerate(self.exchanges)
                if exchange.get("ok") and i not in self.consumed]


def event_rows(result):
    ledger = result.get("event_log") or result.get("onset_event_log") or {}
    return ledger.get("events", []) if isinstance(ledger, dict) else ledger


def world_snapshots(result):
    """Deduplicate onset spans copied into final composition by stage and ID."""
    worlds = {}
    for row in (result.get("onset_worlds") or []) + (result.get("causal_worlds") or []):
        worlds[(row["stage"], row["chrono_id"])] = row
    return worlds


def check_world(scene, check):
    """Evaluate fixture-authored structural assertions, without prose matching."""
    kind = check["kind"]
    entity = check.get("entity")
    expected = check.get("equals")
    if kind == "path":
        actual = scene
        for part in check["path"]:
            actual = actual.get(part) if isinstance(actual, dict) else None
    elif kind == "parent":
        actual = (scene.get("contained", {}).get(entity) or {}).get("in")
    elif kind == "room":
        from world.spatial import room_of
        actual = room_of(scene, entity)
    elif kind == "station":
        actual = (scene.get("stations", {}).get(entity) or {}).get("at")
    elif kind == "no_grip":
        from world.spatial import bearing_contact_holder
        # A mechanical clip gripping its mount is a valid attachment. This
        # check concerns a released person's retained grasp, not any contact.
        actual = not any(bearing_contact_holder(scene, row, entity)
                         for row in scene.get("contacts", []))
        expected = True
    elif kind == "entity_count":
        actual = sum(row.get("name") == check["name"]
                     for row in scene.get("entities", {}).values() if isinstance(row, dict))
    else:
        raise ValueError("Unknown world assertion: " + kind)
    matches = actual == expected
    if (not matches and kind == "path" and len(check["path"]) == 3
            and check["path"][0] == "poses" and check["path"][2] == "posture"
            and actual and expected):
        from world.spatial import posture_class
        name = check["path"][1]
        matches = posture_class(scene, name) == posture_class(
            {"poses": {name: {"posture": expected}}}, name)
    if not matches and kind in ("parent", "station") and actual and expected:
        from world.spatial import same_subject
        matches = same_subject(scene, actual, expected)
    return {"check": check, "actual": actual,
            "status": "pass" if matches else "fail"}


def score_result(result, alignment=None):
    """Keep unreviewed events separate from passed physical/quotation checks."""
    expected = result["case"].get("expectations", {})
    worlds = world_snapshots(result)
    checks = []
    for event in expected.get("events", []):
        mapped = (alignment or {}).get(event["id"])
        world = worlds.get((mapped.get("stage"), mapped.get("chrono_id"))) if mapped else None
        if not world or (mapped or {}).get("state_observable") is False:
            checks.append({"event": event["id"], "status": "unreviewed",
                           "reason": (mapped or {}).get("reason") or "No reviewed chronological boundary"})
            continue
        for check in event.get("checks", []):
            checks.append(dict(check_world(world["after"], check), event=event["id"], boundary=mapped))
        if not event.get("checks"):
            checks.append({"event": event["id"], "status": "reviewed", "boundary": mapped})
    final = result.get("final_scene") or result.get("onset_scene") or {}
    for check in expected.get("final", []):
        checks.append(dict(check_world(final, check), scope="final"))
    for excluded in expected.get("non_events", []):
        for check in excluded.get("checks", []):
            checks.append(dict(check_world(final, check), scope="non_event",
                               description=excluded["description"]))
    speeches = [(row.get("actor"), row.get("text", row.get("account", "")))
                for row in event_rows(result) if row.get("kind") == "speech"]
    def quote_form(text):
        text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'}))
        return " ".join(text.strip().strip('"').split()).rstrip(".,!?:;")
    remaining = list(speeches)
    for quote in expected.get("quotes", []):
        match = next((i for i, (speaker, text) in enumerate(remaining)
                      if speaker == quote["speaker"] and quote_form(text) == quote_form(quote["text"])), None)
        checks.append({"quote": quote, "status": "pass" if match is not None else "fail"})
        if match is not None:
            remaining.pop(match)
    return {"case": result["case"]["id"], "checks": checks,
            "counts": {status: sum(check["status"] == status for check in checks)
                       for status in ("pass", "fail", "unreviewed", "reviewed")},
            "unmatched_speech": remaining, "execution_error": result.get("error")}


def readable_log(result):
    lines = ["# " + result["case"]["id"], "", result["case"]["prose"], "", "## Recompiled events", ""]
    for row in event_rows(result):
        text = row.get("text") or row.get("account") or row.get("surface") or ""
        lines.append(f"- {row.get('order')}: {row.get('actor', '')} [{row.get('kind', '')}] {text}")
    lines.extend(["", "Intermediate checks require reviewed alignment; event-log coverage alone is not world fidelity.", ""])
    return "\n".join(lines)


def unpack_evidence(bundle_path, out, label):
    """Rehydrate checked-in captures for replay, without any database or keys."""
    bundle = json.loads(Path(bundle_path).read_text())
    corpus = {case["id"]: case for case in bundle["corpus"]["cases"]}
    selected = next(run for run in bundle["runs"] if run["label"] == label)
    target_root = Path(out)
    target_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    target_root.chmod(0o700)
    for result in selected["cases"]:
        case_id = result["case_id"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", case_id):
            raise ValueError("Case IDs must be safe directory names")
        target = target_root / case_id
        target.mkdir(mode=0o700, exist_ok=False)
        restored = deepcopy(result)
        restored["case"] = corpus[case_id]
        for exchange in restored["exchanges"]:
            digest = exchange.get("system_sha256")
            if digest:
                exchange["system"] = bundle["prompts"][digest]
        save_artifact(target / "result.json", restored)
        save_artifact(target / "exchanges.json", restored["exchanges"])
    save_artifact(target_root / "corpus.json", bundle["corpus"])


def run_case(case, args):
    """Execute the existing engine entry points and preserve all evidence."""
    target = Path(args.out).resolve() / case["id"]
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    replay_source = Path(args.replay_root) / case["id"] if args.replay_root else None
    captured = json.loads((replay_source / "result.json").read_text()) if replay_source else {}
    database = prepare_database(target / "scratch.db", args.source_db,
                                captured.get("settings"), args.provider, args.model)
    # Configure the scratch DB before importing engine modules that may read settings.
    from core import db
    from agents.runtime import compute_step
    from agents.common import preview_player_state_assertions
    from agents.director import beat_event_ledger
    from persist.commit import compose_beat_scene
    ctx = seed_case(case)
    result = {"case": case, "settings": {key: db.get_setting(key) for key in REPLAY_SETTINGS},
              "models": json.loads(db.get_setting("agent_models") or "{}"),
              "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    replayer = CapturedReplies(captured["exchanges"]) if replay_source else None
    started = time.monotonic()
    try:
        with ExitStack() as stack:
            if replayer:
                stack.enter_context(no_network())
                stack.enter_context(patch("agents.director._agent_json", replayer))
            print("START", case["id"], flush=True)
            interp = compute_step("director_interpret", ctx, 0)
            ctx.director_interpret = interp
            result["interpret"] = interp
            save_artifact(target / "interpret.json", interp, database)
            save_artifact(target / "exchanges.json", list(ctx.exchanges), database)
            result["onset_worlds"] = []
            result["onset_scene"] = preview_player_state_assertions(
                case["scene"], interp.get("onset_state_assertions") or interp.get("state_assertions"),
                ctx, case["primary_name"], causal_worlds=result["onset_worlds"])
            result["onset_event_log"] = beat_event_ledger({}, interp, [])
            ctx.perception_act = compute_step("perception_act", ctx, 0)
            result["perception_act"] = ctx.perception_act
            if not args.interpret_only:
                ctx.director_resolve = compute_step("director_resolve", ctx, 0)
                result["resolve"] = ctx.director_resolve
                composed = compose_beat_scene(ctx)
                result.update(final_scene=composed.scene, causal_worlds=composed.causal_worlds,
                              event_log=composed.scene.get("beat_events"))
                result["perception_outcome"] = compute_step("perception_outcome", ctx, 0)
    except Exception:
        result["error"] = traceback.format_exc()
    result.update(seconds=round(time.monotonic() - started, 2), warnings=list(ctx.warnings),
                  calls=list(ctx.llm_calls), exchanges=list(ctx.exchanges), decisions=list(ctx.decisions),
                  director_notes=list(getattr(ctx, "engine_feedback", [])))
    if replayer:
        result.update(replay_source=str(replay_source), replayed_exchanges=replayer.records,
                      unused_accepted_exchanges=replayer.unused(), captured_exchanges=captured["exchanges"],
                      replay_failures=replayer.failures)
        if replayer.failures or replayer.unused():
            result.setdefault("error", "Replay did not consume exactly the accepted exchanges; see replay diagnostics")
        fields = {field: (result.get("final_scene") or {}).get(field) ==
                  (captured.get("final_scene") or {}).get(field) for field in WORLD_FIELDS}
        result["replay_comparison"] = dict(fields, event_log=result.get("event_log") == captured.get("event_log"))
    result["score"] = score_result(result)
    save_artifact(target / "result.json", result, database)
    save_artifact(target / "exchanges.json", list(ctx.exchanges), database)
    save_artifact(target / "events.md", readable_log(result), database)
    print("DONE", case["id"], result["seconds"], "seconds", len(ctx.llm_calls), "provider calls",
          "ERROR" if result.get("error") else "", flush=True)
    db.close_connection()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    run.add_argument("--out", required=True, type=Path)
    source = run.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-db", type=Path)
    source.add_argument("--replay-root", type=Path)
    run.add_argument("--case", action="append", default=[])
    run.add_argument("--provider", choices=("openrouter", "nanogpt"))
    run.add_argument("--model")
    run.add_argument("--interpret-only", action="store_true")
    score = commands.add_parser("score")
    score.add_argument("--root", required=True, type=Path)
    score.add_argument("--alignment", type=Path)
    unpack = commands.add_parser("unpack")
    unpack.add_argument("--bundle", required=True, type=Path)
    unpack.add_argument("--out", required=True, type=Path)
    unpack.add_argument("--run", choices=("initial", "regression"), default="initial")
    args = parser.parse_args(argv)
    if args.command == "unpack":
        unpack_evidence(args.bundle, args.out, args.run)
        return 0
    if args.command == "score":
        alignment = json.loads(args.alignment.read_text()) if args.alignment else {}
        for path in sorted(args.root.glob("*/result.json")):
            result = json.loads(path.read_text())
            scored = score_result(result, alignment.get(result["case"]["id"]))
            save_artifact(path.parent / "score.json", scored,
                          path.parent / "scratch.db" if (path.parent / "scratch.db").exists() else None)
            print(scored["case"], scored["counts"])
        return 0
    if bool(args.provider) != bool(args.model) or (args.replay_root and args.provider):
        parser.error("--provider and --model must be supplied together, on live runs only")
    cases = load_cases(args.corpus, args.case)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.out.chmod(0o700)
    failed = False
    for case in cases:
        if (args.out / "STOP_AFTER_CURRENT").exists():
            break
        failed |= bool(run_case(case, args).get("error"))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
