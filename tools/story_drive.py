#!/usr/bin/env python3
"""Play a real story, with the author of this file standing in for the model.

Every off-screen and crowd mechanism in the 8.0 line reports `no chances`,
because the live corpus predates the code and nothing has been PLAYED against
it. `tools/offscreen_drive.py` and `tools/crowd_drive.py` answer a different
question -- they call commit domains directly, which proves the machinery works
and produces no turns. Fire rates read commit blobs from real beats, so they
stay at zero however many harnesses pass.

This runs the ACTUAL pipeline. `agents.runtime.run_pipeline` executes every
stage in order against a real turn row; the only thing replaced is
`providers.chat_complete`, which returns authored payloads instead of calling
a model. So the schemas validate for real, `commit_all` runs for real, and the
commit results `tools/fire_rates.py` reads are the ones a played story writes.

WHAT THIS CAN AND CANNOT PROVE. It shows the mechanisms fire when a Director
declares them, and it produces a corpus fire rates can measure. It CANNOT tell
you whether a real model WOULD declare them -- the payloads here are written by
hand, so asking this harness how often crowds appear is asking whether the
author typed one. That number moves only when a model plays, and the prompt
work is what moves it.

Writes only to its own scratch database and refuses to start against anything
that looks like the author's.

    ENGINE_DB=/path/to/scratch.db python3 tools/story_drive.py
    ENGINE_DB=/path/to/scratch.db python3 tools/story_drive.py --json
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.offscreen_drive import _require_scratch  # noqa: E402

HALL, YARD, MARKET = "gate_hall", "inner_yard", "market_square"


def scene():
    """Three rooms with real sizes, because crowd density is derived from them.

    An unsized room reads `medium`, which would make every crowd in this story
    the same density and quietly prove nothing.
    """
    return {
        "location": "Lugunica",
        "time": "afternoon",
        "rooms": {
            HALL: {"name": "Gate Hall", "size": "small",
                   "adjacent": [{"to": YARD, "barrier": "open"}]},
            YARD: {"name": "Inner Yard", "size": "large",
                   "adjacent": [{"to": HALL, "barrier": "open"},
                                {"to": MARKET, "barrier": "open"}]},
            MARKET: {"name": "Market Square", "size": "huge",
                     "adjacent": [{"to": YARD, "barrier": "open"}]},
        },
        # Mora and Kestrel share a room, because a telling is a thing that
        # happens somewhere and the engine refuses one across a doorway.
        "positions": {"Nathan": HALL, "Mora": HALL, "Kestrel": HALL},
        "entities": {},
    }


def build_story(db):
    """A story configured for every floor, with a dormant mind left behind.

    Each setting is deliberate. The live corpus has them off or absent, which
    was one of four independent reasons nothing had ever fired, and a harness
    that inherited the defaults would faithfully reproduce that silence.
    """
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Story drive", "A gate town on the day the riders come.",
                 time.time()))

    def cast(name, uid, status, agent=False):
        sheet = {
            "identity": {"name": name, "uid": uid},
            "psychology": {"drive": {"essence": "keep the gate shut"},
                           "traits": {"wary": 0.7}},
            "simulation": {"tier": "major",
                           **({"offscreen_agent": True} if agent else {})},
        }
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
              "VALUES(?,?,?,'{}',NULL)", (cid, char_id, status))
        return char_id

    cast("Mora", "mora_uid", "active")
    cast("Kestrel", "kestrel_uid", "active")
    # Left behind and opted in: the only shape that can reach the paid rung.
    cast("Otto", "otto_uid", "dormant", agent=True)

    db.wset(cid, "scene", scene())
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    db.wset(cid, "dialogue_config",
            {"offscreen_life": "stochastic", "max_offscreen_actors": 3})
    db.wset(cid, "living_world", {
        "routine_residue": "floor", "scheduled_consequence": "floor",
        "place_obligations": "floor", "antagonist_ladder": "floor",
        "rumor_ledger": "floor",
    })
    return cid


# --------------------------------------------------------------- the model

def _base(stage):
    from schemas import OUTPUT_EXAMPLES

    return copy.deepcopy(OUTPUT_EXAMPLES.get(stage) or {})


def _blank_diff():
    """A state_diff that changes nothing, in the shape validation expects."""
    diff = _base("director_resolve").get("state_diff") or {}
    for key, value in list(diff.items()):
        if isinstance(value, list):
            diff[key] = []
        elif isinstance(value, dict) and key != "time":
            diff[key] = {}
    diff["time"] = {"start_seconds": 0, "duration_seconds": 30,
                    "end_seconds": 30, "mode": "action", "explicit": False,
                    "display_advance": ""}
    return diff


class Author:
    """Stands in for every model call, and records what it was asked.

    Keyed by ROLE rather than by turn, with per-turn overrides, so a script
    only has to write the payload that carries the beat it cares about. The
    rest fall back to something valid and inert -- a harness whose default is
    to change nothing cannot accidentally prove a mechanism fired.
    """

    def __init__(self):
        self.turn_script = {}
        self.calls = []
        self.rejected = []

    def script(self, turn_idx, role, payload):
        self.turn_script.setdefault(turn_idx, {})[role] = payload

    def __call__(self, *, role, step_key, system, payload, **kw):
        """Stands in for `llm_quality.complete_validated_json`.

        Deliberately NOT a stub. The authored payload goes through
        `validate_llm_output_strict` exactly as a model's would, so a beat
        written here that the schema would reject fails here too -- which is
        the whole reason to run the real pipeline rather than call commit
        domains directly. A harness that skipped validation would prove the
        commit path works on data no model could ever send.
        """
        from schemas import validate_llm_output_strict

        self.calls.append(step_key)
        authored = self._for(step_key)
        if callable(authored):
            authored = authored(payload)
        report = validate_llm_output_strict(step_key, authored,
                                            source_payload=payload)
        if not report.valid:
            self.rejected.append({"step": step_key,
                                  "errors": list(report.errors)[:3]})
            return authored
        return report.output

    def current_turn(self, idx):
        self._turn = idx

    def _for(self, step_key):
        scripted = (self.turn_script.get(getattr(self, "_turn", -1)) or {})
        base = step_key.split(":")[0]
        if base in scripted:
            return scripted[base]
        if step_key in scripted:
            return scripted[step_key]
        return self.default(base)

    def default(self, role):
        if role == "director_interpret":
            # `sequence is empty despite nonempty player input` -- the
            # interpret stage must actually interpret something.
            def interpret(payload):
                said = str((payload or {}).get("player_input") or "waits")
                out = _base("director_interpret")
                out["kind"] = "action"
                out["sequence"] = [{"type": "action", "attempt": said}]
                return out
            return interpret
        if role == "director_establish":
            # Establish OWNS the opening scene, and its shape is NOT the
            # resolve shape: rooms and positions sit at the top level and
            # there is no `state_diff` at all. Building it from the resolve
            # payload handed the story somebody else's rooms -- the committed
            # scene came back as "Armory", and every crowd op afterwards
            # landed in a room that did not exist. The engine was right to
            # refuse them; the harness was wrong.
            world = scene()
            out = _base("director_establish")
            out["location"] = world["location"]
            out["time"] = world["time"]
            out["scene_description"] = "The gate hall, loud with afternoon."
            out["rooms"] = {
                rid: {"name": r["name"], "adjacent": r["adjacent"],
                      "size": r["size"]}
                for rid, r in world["rooms"].items()}
            out["positions"] = dict(world["positions"])
            out["entities"] = {}
            out["crowd_ops"] = [{
                "op": "set", "room": MARKET, "band": "a throng",
                "composition": "traders and gate traffic",
                "mood": "restless"}]
            return out
        if role in ("director_resolve", "director_establish"):
            out = _base("director_resolve")
            out["state_diff"] = _blank_diff()
            out["resolved_event"] = "Nothing in particular happens."
            out["dialogue_log"] = []
            out["dialogue_order"] = []
            for key in ("changes_asserted", "dice", "obligations",
                        "fact_adjudications"):
                out[key] = []
            return out
        if role == "narrator":
            return {"prose": "The gate hall is quiet."}
        if role == "perception":
            # `views is missing perceiver IDs` -- perception must answer for
            # exactly the perceivers it was handed, so this reads them off the
            # payload rather than guessing.
            def views(payload):
                ids = []
                for key in ("perceivers", "observers", "views"):
                    value = (payload or {}).get(key)
                    if isinstance(value, list):
                        ids = [str(v.get("id") if isinstance(v, dict) else v)
                               for v in value]
                        break
                    if isinstance(value, dict):
                        ids = [str(k) for k in value]
                        break
                return {"views": {i: {"summary": "The hall is busy.",
                                      "sensed": [], "unknowns": []}
                                  for i in ids}}
            return views
        if role == "character":
            out = _base("character")
            out["sequence"] = []
            for key in ("relationship_updates", "belief_updates",
                        "memory_effects", "mind_model_updates"):
                if key in out:
                    out[key] = []
            return out
        return _base(role) or {}


# ------------------------------------------------------------------ the play

#: What a character says out loud on a given beat, by turn index.
SPEECH = {4: "They barred it against forty riders in the Market Square."}


def standing_uid(cid):
    """The uid of the crowd currently standing, as perception would show it.

    A Director never invents a crowd_id -- it reads one off its own payload,
    and `crowds.apply_ops` refuses any id the engine did not mint. The script
    has to do the same or it is testing a Director that cheats.
    """
    import db

    for crowd in db.wget(cid, "crowds", []) or []:
        if isinstance(crowd, dict) and crowd.get("uid"):
            return str(crowd["uid"])
    return ""


def turns(author, cid):
    """The beats, and what the Director declares on each.

    Written to exercise the things the completion doc asks to see, in the order
    a story would actually produce them: a place fills, someone is caught in
    it, a consequence is set running, news of it reaches one mind and not
    another, and the mind that heard it passes it on.
    """
    market_crowd = {
        "op": "set", "room": MARKET, "band": "a throng",
        "composition": "traders and gate traffic", "mood": "restless"}

    def resolve(**over):
        out = author.default("director_resolve")
        diff = out["state_diff"]
        for key, value in over.pop("diff", {}).items():
            diff[key] = value
        out.update(over)
        return out

    script = [
        # 1. The player walks into the crowd the opening established.
        ("I walk out to the market.",
         resolve(resolved_event="The square is packed with traders.",
                 diff={"positions": {"Nathan": MARKET}})),
        # 2. The press starts moving toward the yard. Declared, not spent yet:
        #    a heading lives one beat of perception so the Director can be
        #    shown a drift and asked to resolve it.
        ("I try to push through toward the yard.",
         lambda _p: resolve(
             resolved_event="The crowd begins to move toward the yard.",
             diff={"crowd_ops": [{"op": "set",
                                  "crowd_id": standing_uid(cid),
                                  "heading": YARD}]})),
        # 3. An hour of work: the clock crosses the epoch bucket that a
        #    twenty-second beat never reaches.
        ("I spend the afternoon helping bar the gate.",
         resolve(resolved_event="The afternoon goes into the gate.",
                 diff={"time": {"start_seconds": 60,
                                "duration_seconds": 5400,
                                "end_seconds": 5460, "mode": "time_skip",
                                "explicit": True,
                                "display_advance": "an hour and a half"}})),
        # 4. A consequence set running offscreen, with a public surface.
        ("I tell Mora to send word to the yard.",
         resolve(resolved_event="Mora sets off to carry word.",
                 dialogue_log=[{"speaker": "Mora",
                                "text": "I'll tell them myself."}],
                 diff={"consequences": [{
                     "what": "the yard gate stands barred",
                     "where": YARD, "due_seconds": 3600,
                     "witnessed": "the gate was barred from inside",
                     "originator": "Mora"}]})),
        # 5. Mora passes on what she saw. Kestrel is in the yard; Otto is
        #    dormant and is told nothing by anybody.
        ("I ask Mora what she saw out there.",
         resolve(resolved_event="Mora tells Kestrel about the gate.",
                 dialogue_log=[{"speaker": "Mora",
                                "text": "They barred it from the inside."}],
                 diff={"telling_ops": [{
                           "speaker": "Mora", "listener": "Kestrel",
                           # No event backs this one: Mora is repeating what
                           # she believes, and it enters through the same
                           # physics as the truth.
                           "claim": "Kestrel barred the gate against forty "
                                    "riders in the Market Square"}]})),
        # 6. A knot peels off toward the yard.
        ("I watch the crowd break up.",
         lambda _p: resolve(
             resolved_event="A knot of them peels away toward the yard.",
             diff={"crowd_ops": [{"op": "split",
                                  "crowd_id": standing_uid(cid),
                                  "heading": YARD}]})),
    ]
    return script


def play(db, cid, author):
    """Run each beat through the real pipeline and keep what commit reported."""
    from agents.runtime import run_pipeline

    played = []
    for idx, (player_input, resolved) in enumerate(turns(author, cid)):
        author.script(idx, "director_resolve", resolved)
        line = SPEECH.get(idx)
        if line:
            # A telling is grounded on `dialogue_log`, and in an
            # interaction-loop turn that log is assembled from what the
            # CHARACTERS actually said -- not from what the Director wrote in
            # its own payload. Scripting the resolve alone left the log empty
            # and the telling correctly refused: nobody had spoken.
            spoken = dict(author.default("character"))
            spoken["sequence"] = [{"type": "speech", "text": line}]
            author.script(idx, "character", spoken)
        # Turn 0 is an opening: establish authors the scene and the beat's own
        # resolve declarations do not apply to it.
        author.current_turn(idx)
        tid = db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (cid, idx, player_input, time.time(), None))
        error = ""
        try:
            for _ in run_pipeline(cid, tid):
                pass
        except Exception as exc:              # noqa: BLE001 - reported, not hidden
            error = "%s: %s" % (type(exc).__name__, exc)
        played.append({"turn": idx, "input": player_input, "error": error})
    return played


def commit_results(db, cid):
    """What the commit domains actually reported, per turn.

    Read back from the stored commit step rather than from the return value,
    because that row is exactly what `tools/fire_rates.py` will read.
    """
    rows = db.q(
        "SELECT s.turn_id, v.content FROM variants v "
        "JOIN steps s ON s.id = v.step_id "
        "WHERE v.active=1 AND s.key='commit' ORDER BY s.turn_id") or []
    out = []
    for row in rows:
        try:
            blob = json.loads(row["content"])
        except (TypeError, ValueError):
            continue
        results = (blob or {}).get("results") or {}
        out.append({k: results.get(k) for k in
                    ("crowds", "information_carriers", "offscreen_epoch",
                     "offscreen_plans", "world_events") if k in results})
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    path = _require_scratch()
    import db as db_module
    import providers

    db_module.init()
    author = Author()
    import llm_quality
    llm_quality.complete_validated_json = author
    # Every stage imports it by name at module load, so the already-bound
    # references have to be replaced too.
    for mod in list(sys.modules.values()):
        if getattr(mod, "complete_validated_json", None) is not None \
                and mod is not llm_quality:
            mod.complete_validated_json = author

    cid = build_story(db_module)
    played = play(db_module, cid, author)
    report = {"database": path, "chat_id": cid, "turns": played,
              "schema_rejections": author.rejected,
              "commit_results": commit_results(db_module, cid),
              "stages_called": sorted(set(author.calls))}

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print("story drive — real turns, authored payloads\n")
    for t in played:
        mark = "ok " if not t["error"] else "ERR"
        print("  [%s] turn %d  %s" % (mark, t["turn"], t["input"]))
        if t["error"]:
            print("        %s" % t["error"])
    print("\n  stages exercised: %s" % ", ".join(report["stages_called"]))
    if author.rejected:
        print("\n  authored payloads the SCHEMA refused:")
        for r in author.rejected[:6]:
            print("    %-22s %s" % (r["step"], r["errors"]))
    print("\n  commit results per turn:")
    for i, res in enumerate(report["commit_results"]):
        print("    turn %d: %s" % (i, json.dumps(res)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
