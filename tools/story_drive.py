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
    # A REAL persona. Without one `persona_of` falls back to "The Stranger",
    # who then appears in `positions` as a body nobody authored -- and, worse,
    # the player has no room, so `schedule_profile_ticks` skips every epoch
    # with `no_player_room` and the distance axis has no anchor at all. The
    # medium rung cannot be reached by a story with no player in it.
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Nathan", json.dumps({
            "name": "Nathan",
            "appearance": "A traveller in a dust-coloured coat.",
            "senses": "ordinary senses", "abilities": [],
            "public_history": "", "private_history": ""}), "{}"))
    cid = db.qi("INSERT INTO chats(name,scenario,created,persona_id) "
                "VALUES(?,?,?,?)",
                ("Story drive", "A gate town on the day the riders come.",
                 time.time(), persona_id))

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
    # Opted in, and the only cast member who acquires a REASON during the
    # story: he is told something on turn 11, declares a plan on turn 12, and
    # walks out on turn 15. `full_agent_candidates` wants exactly that -- an
    # active plan of his own, or evidence newer than his last tick. A mind
    # with neither is declined with `no_private_reason`, which is the rung
    # refusing to pay for a character who has nothing to think about.
    cast("Kestrel", "kestrel_uid", "active", agent=True)
    # Left behind and opted in: the only shape that can reach the paid rung.
    cast("Otto", "otto_uid", "dormant", agent=True)

    db.wset(cid, "scene", scene())
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    # The CEILING, not the floor. `character_agent` is the top rung and the
    # only one that pays for an absent mind to think; a story left at
    # `stochastic` can never reach it however many epochs fire.
    db.wset(cid, "dialogue_config",
            {"offscreen_life": "character_agent", "max_offscreen_actors": 3})
    db.wset(cid, "living_world", {
        "routine_residue": "floor", "scheduled_consequence": "floor",
        "place_obligations": "floor", "antagonist_ladder": "ceiling",
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
        import threading
        self.turn_script = {}
        self.calls = []
        self.rejected = []
        self.capture_dir = ""
        self._capture_lock = threading.Lock()
        self._capture_seen = {}

    def _capture(self, step_key, system, payload):
        """Write out exactly what a model would be handed.

        For reading BY a model, cold, to find out what the prompt actually
        communicates as opposed to what it was meant to. No test can ask that
        question; it is the one thing only a reader can answer.

        One file per CALL, not per turn-and-stage. The off-screen rungs run on
        daemon threads and reach this seam while the foreground turn is still
        in it, so two writers shared a filename: the shorter document landed
        inside the longer one and five captures in a fifty-one beat run were
        not parseable at all. A scan cannot tell that apart from the engine
        emitting malformed context, which is the wrong thing to go looking
        for. Same-name calls get `.2`, `.3`, in the order they arrived.
        """
        import os
        os.makedirs(self.capture_dir, exist_ok=True)
        name = "t%02d_%s" % (getattr(self, "_turn", -1), step_key.replace(":", "_"))
        with self._capture_lock:
            self._capture_seen[name] = self._capture_seen.get(name, 0) + 1
            nth = self._capture_seen[name]
        if nth > 1:
            name = "%s.%d" % (name, nth)
        base = os.path.join(self.capture_dir, name)
        with open(base + ".system.txt", "w") as fh:
            fh.write(str(system or ""))
        with open(base + ".payload.json", "w") as fh:
            json.dump(payload, fh, indent=1, default=str)

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

        if self.capture_dir:
            self._capture(step_key, system, payload)
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
        if role == "interpret_repair":
            # The SHIPPED example for this stage contains a full worked beat --
            # "duck into the armory", `movement.to_room: "armory"`. Falling
            # back to it meant every repaired interpretation declared a move
            # into a room nobody had authored, and the phantom then anchored
            # the party's movement for the rest of the story. A repair should
            # return the interpretation, not a different story's.
            return self.default("director_interpret")
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
#: Keyed by TURN INDEX, which means inserting a beat silently re-aims every
#: line after it -- and a plan whose speaker did not speak is refused, so the
#: whole antagonist ladder went quiet the first time a beat was added here.
SPEECH = {9: "I saw it barred from the inside.",
          11: "They barred it against forty riders.",
          12: "I'll bar the west gate before dusk."}


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
    """Twenty beats, written so the WORLD gets chances rather than the player.

    The shape matters more than the content. A consequence has to be set
    running early and left alone, or it can never come due; the clock has to
    cross real hours, or no epoch fires; somebody has to be left behind, or
    there is nobody for news to fail to reach. A script where every beat is
    interesting tests nothing, because the quiet beats are where the off-screen
    world is supposed to be doing the work.
    """
    def resolve(**over):
        out = author.default("director_resolve")
        diff = out["state_diff"]
        for key, value in over.pop("diff", {}).items():
            diff[key] = value
        out.update(over)
        return out

    def skip(seconds, label, **over):
        diff = dict(over.pop("diff", {}))
        diff["time"] = {"start_seconds": 0, "duration_seconds": seconds,
                        "end_seconds": seconds, "mode": "time_skip",
                        "explicit": True, "display_advance": label}
        return resolve(diff=diff, **over)

    def crowd_op(said, **op):
        event = op.pop("_event", "The crowd shifts.")
        return (said, lambda _p: resolve(
            resolved_event=event,
            diff={"crowd_ops": [dict(op, crowd_id=standing_uid(cid))]}))

    return [
        # --- the world is set in motion, then largely left alone -----------
        ("I walk out into the square.",
         resolve(resolved_event="The square is packed.",
                 diff={"positions": {"Nathan": MARKET}})),
        ("I ask what the riders want.",
         resolve(resolved_event="Nobody answers straight.")),
        # A consequence with a PUBLIC surface, due in an hour, in a room the
        # party is about to leave. This is the whole point: something that
        # happens where nobody is standing.
        ("I send word that the yard gate must be barred.",
         resolve(resolved_event="Word goes to the yard.",
                 diff={"consequences": [{
                     "what": "the yard gate stands barred",
                     "where": YARD, "due_seconds": 3600,
                     "witnessed": "the gate was barred from the inside",
                     "originator": "Mora"}]})),
        crowd_op("I push toward the yard.", op="set", heading=YARD,
                 _event="The press turns toward the yard."),
        ("I let the crowd carry me.", resolve(
            resolved_event="The press moves.")),
        ("I wait for it to thin.", skip(1800, "half an hour")),
        # Now the clock crosses the hour the consequence was due in.
        ("I spend the afternoon at the gate.", skip(5400, "an hour and a half")),
        ("I go back through to the yard.",
         resolve(resolved_event="The yard is quiet.",
                 diff={"positions": {"Nathan": YARD, "Mora": YARD}})),
        ("I look at the gate.", resolve(
            resolved_event="It is barred, from the inside.")),
        ("I ask Mora if she saw who did it.", resolve(
            resolved_event="Mora says what she saw.")),
        # Mora passes on what she is carrying. The Director now has the ids.
        ("We walk back to the hall.",
         resolve(resolved_event="The hall is where Kestrel waited.",
                 diff={"positions": {"Nathan": HALL, "Mora": HALL}})),
        ("I ask her to tell Kestrel.", lambda payload: resolve(
            resolved_event="Mora tells Kestrel.",
            diff={"telling_ops": [
                {"speaker": "Mora", "listener": "Kestrel",
                 "world_event_id": _first_report_id(payload)}]}
            if _first_report_id(payload) else {})),
        ("I ask Kestrel what he means to do.",
         resolve(resolved_event="Kestrel says what he intends.",
                 diff={"offscreen_plan_ops": [{
                     "op": "open", "plan_id": "bar-the-west-gate",
                     "actor": "Kestrel",
                     "objective": "Bar the west gate before dusk",
                     "basis": "I'll bar the west gate before dusk",
                     "stages": [{
                         "stage_id": "bar-it",
                         "trigger": {"after_seconds": 1800},
                         "effect": {
                             "what": "the west gate stands barred",
                             "where": YARD, "due_seconds": 0,
                             "witnessed": "the west gate was barred",
                             "originator": "Kestrel"}}]}]})),
        ("I check the market again.",
         resolve(resolved_event="Fewer of them now.",
                 diff={"positions": {"Nathan": MARKET}})),
        crowd_op("I watch them break up.", op="split", heading=YARD,
                 _event="A knot peels away."),
        ("I follow the ones going to the yard.",
         resolve(resolved_event="They spill through.",
                 diff={"positions": {"Nathan": YARD}})),
        # Kestrel walks out. He has been beside the player for fifteen beats,
        # so `subject_last_seen` anchors him NEAR rather than nowhere -- which
        # is what lets the medium rung consider him at all. A dormant mind who
        # was never co-present reads `elsewhere`, and major+elsewhere is `low`
        # by design: "a major antagonist three continents away does not need
        # medium".
        ("I watch Kestrel go.",
         resolve(resolved_event="Kestrel goes back through the gate.",
                 diff={"cast_changes": [{"who": "Kestrel", "status": "dormant",
                                         "reason": "walked out to the wall"}]})),
        ("I sit down and wait.", skip(3600, "an hour")),
        ("I sleep until dawn.", skip(28800, "the night")),
        ("I walk the wall.", resolve(resolved_event="The wall is cold.")),
        ("I go back to the square.",
         resolve(resolved_event="It is filling again.",
                 diff={"positions": {"Nathan": MARKET}})),
        crowd_op("I call out to the crowd.", op="emerge",
                 who="a rope-seller",
                 _event="A rope-seller steps out of the press."),
        ("I ask the rope-seller what he heard.", resolve(
            resolved_event="He says the gate was barred against forty riders.")),
    ]


def _first_report_id(payload):
    """A world_event_id the Director can actually see in its own payload.

    Reading it off the payload rather than out of the database is the point:
    if the Director cannot find one here, no model could either, and the
    telling should fail exactly as it would in a real game.
    """
    for row in ((payload or {}).get("carried_reports") or []):
        if isinstance(row, dict) and row.get("world_event_id"):
            return str(row["world_event_id"])
    return ""


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
    ap.add_argument("--capture", default="",
                    help="directory to write each stage's system prompt and "
                         "payload into, for reading as the model")
    args = ap.parse_args()

    path = _require_scratch()
    import db as db_module
    import providers

    db_module.init()
    author = Author()
    author.capture_dir = args.capture
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
