#!/usr/bin/env python3
"""One rider, two endings, played twice through the real pipeline.

The courier layer's honesty test, run as a story rather than as unit tests:
Maelor, in his keep, puts a lie on a rider bound for Siege Town. The rider is
a body with a position, so the same script forks at the moment Corin stands on
the road watching him pass:

- **delivery**: Corin lets him by. The rider reaches the town and the lie
  arrives -- two mouths fainter, attributed to "a rider in ash-grey", never to
  Maelor.
- **interception**: Corin drags him off his horse. The lie never arrives
  anywhere, which is the entire point of a route existing.

Every model output is authored; every mechanism that fires is the engine's
own. What this proves is that the machinery fires when a Director declares it,
including the perception half: the beat-by-beat log shows the rider entering
the player's OWN perception payload as he passes -- interception is only real
because somebody could see the man.

Writes only to its own scratch database.

    ENGINE_DB=/path/to/scratch.db python3 tools/courier_drive.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.offscreen_drive import _require_scratch  # noqa: E402
from tools.story_drive import Author, _base, _blank_diff  # noqa: E402

KEEP, GATE, ROAD, TOWN = "ashen_keep", "citadel_gate", "old_road", "siege_town"

ROOMS = {
    KEEP: ("The Ashen Keep",  "medium", [GATE]),
    GATE: ("The Citadel Gate", "small",  [KEEP, ROAD]),
    ROAD: ("The Old Road",     "large",  [GATE, TOWN]),
    TOWN: ("Siege Town",       "large",  [ROAD]),
}

THE_LIE = ("three wells at Siege Town were poisoned by "
           "the boy from the Fenwater")


def scene():
    rooms = {}
    for rid, (name, size, adj) in ROOMS.items():
        rooms[rid] = {"name": name, "size": size,
                      "adjacent": [{"to": t, "barrier": "open"} for t in adj]}
    return {
        "location": "The Vale, eastern reach",
        "time": "morning",
        "rooms": rooms,
        "positions": {"Corin": ROAD, "Maelor": KEEP, "Bryn": TOWN},
        "entities": {},
    }


def build_story(db):
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Corin", json.dumps({
            "name": "Corin",
            "appearance": "A young smith's apprentice on the road east.",
            "senses": "ordinary senses", "abilities": [],
            "public_history": "", "private_history": ""}), "{}"))
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("The Rider", "Maelor sends word ahead of the boy walking east.",
         time.time(), persona_id))

    def cast(name, uid):
        sheet = {"identity": {"name": name, "uid": uid},
                 "psychology": {"drive": {"essence": "endure"}}}
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,'{}')", (cid, char_id, "active"))

    cast("Maelor", "maelor_uid")
    cast("Bryn", "bryn_uid")
    db.wset(cid, "scene", scene())
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    db.wset(cid, "living_world", {"rumor_ledger": "floor"})
    return cid


class RoadAuthor(Author):
    """Authors the road's own opening, and keeps every payload it was shown.

    The kept payloads are the demonstration: the resolve payload must contain
    the courier's uid before an op can name it, and the perception payload
    must contain the rider before anyone can be said to have seen him.
    """

    def __init__(self):
        super().__init__()
        self.seen = {}

    def __call__(self, *, role, step_key, system, payload, **kw):
        # A LIST per turn, not a dict: perception fans out one call per
        # observer under the same step key, and keeping only the last call
        # kept whichever OBSERVER happened to run last -- the player's own
        # payload was captured and then overwritten.
        self.seen.setdefault(getattr(self, "_turn", -1), []).append(
            (step_key, payload))
        return super().__call__(role=role, step_key=step_key, system=system,
                                payload=payload, **kw)

    def default(self, role):
        if role == "director_establish":
            world = scene()
            out = _base("director_establish")
            out["location"] = world["location"]
            out["time"] = world["time"]
            out["scene_description"] = "The old road, and a keep behind it."
            out["rooms"] = {
                rid: {"name": r["name"], "adjacent": r["adjacent"],
                      "size": r["size"]}
                for rid, r in world["rooms"].items()}
            out["positions"] = dict(world["positions"])
            out["entities"] = {}
            return out
        return super().default(role)


def beats(intercept):
    """The shared script, forking at the beat where road and rider meet.

    `state_diff.time.end_seconds` is an ABSOLUTE clock position, not a delta
    (commit honours the larger of end and was+duration): the first draft of
    this script wrote per-beat deltas, the clock therefore barely moved, and
    the rider never left the keep until one huge skip teleported him through
    every beat that was supposed to show him travelling. The running `clock`
    closure keeps every beat's assertion cumulative and honest.
    """
    clock = {"now": 0.0}

    def R(prose, seconds=30, **over):
        out = _base("director_resolve")
        out["state_diff"] = _blank_diff()
        diff = out["state_diff"]
        start = clock["now"]
        clock["now"] = start + seconds
        diff["time"] = {"start_seconds": start, "duration_seconds": seconds,
                        "end_seconds": clock["now"],
                        "mode": "time_skip" if seconds > 120 else "action",
                        "explicit": seconds > 120, "display_advance": ""}
        for key, value in over.pop("diff", {}).items():
            diff[key] = value
        out["resolved_event"] = prose
        for key in ("changes_asserted", "dice", "obligations",
                    "fact_adjudications", "dialogue_log", "dialogue_order"):
            out.setdefault(key, [])
        out.update(over)
        return out

    def courier_here(p, room):
        for row in (p or {}).get("couriers") or []:
            if str(row.get("at")) == room:
                return str(row.get("courier_id") or "")
        return ""

    B = [
        ("I take the road east.",
         R("The road runs empty between the keep and the town.")),
        # Maelor pays for a rider. The claim is his own invention -- a lie
        # entering the network at a point in space, exactly as §9.2 demands.
        ("I look back at the keep on the ridge.",
         R("Smoke stands over the Ashen Keep. A gate opens somewhere.",
           seconds=120,
           diff={"courier_ops": [{
               "op": "send", "sender": "Maelor", "to_room": TOWN,
               "claim": THE_LIE, "method": "word", "pace": "riding",
               "description": "a rider in ash-grey"}]})),
        ("I walk on and watch the ridge road.",
         R("A grey rider comes down from the keep toward the gate.",
           seconds=240)),
        ("I wait where the road narrows.",
         R("The rider clears the gate and comes on, in no hurry.",
           seconds=240)),
    ]
    if intercept:
        # The op names the uid the RESOLVE PAYLOAD showed -- an id the
        # Director was never delivered would be this engine's oldest class
        # of unreachable mechanism. The beat itself is PREBUILT so the
        # cumulative clock advances at script time like every other beat;
        # calling R() inside the callable stamped it with a clock the
        # closure had already run to the end of the story.
        import copy as _copy

        prebuilt = R("Corin takes the rider down in the dust. The message "
                     "dies on the road with him.", seconds=60)

        def take_him(p):
            uid = courier_here(p, ROAD)
            out = _copy.deepcopy(prebuilt)
            if uid:
                out["state_diff"]["courier_ops"] = [{
                    "op": "silence", "by": "Corin", "courier_id": uid}]
            return out
        take_him.prose = prebuilt["resolved_event"]
        B += [("I drag the rider from his horse before he can pass.",
               take_him)]
    else:
        B += [
            ("I step aside and let him pass.",
             R("The rider goes by without a glance, east toward the town.",
               seconds=240)),
        ]
    B += [
        ("I follow the road to Siege Town.",
         R("Siege Town takes Corin in at dusk.", seconds=3600,
           diff={"positions": {"Corin": TOWN}})),
        ("I find Bryn and ask what news came today.",
         R("Bryn tells Corin what the town has heard, which may be nothing.")),
    ]
    return B


def play(db, cid, author, script):
    from agents.runtime import run_pipeline

    played = []
    for idx, (player_input, payload) in enumerate(script):
        author.script(idx, "director_resolve", payload)
        prose = (payload.get("resolved_event") if isinstance(payload, dict)
                 else getattr(payload, "prose", None))
        if prose:
            author.script(idx, "narrator", {"prose": prose})
        moved_to = ((payload.get("state_diff") or {}).get("positions") or {}
                    ).get("Corin") if isinstance(payload, dict) else None
        if moved_to:
            interp = author.default("director_interpret")
            if callable(interp):
                interp = interp({"player_input": player_input})
            interp["movement"] = {"to_room": moved_to, "manner": "walk"}
            author.script(idx, "director_interpret", interp)
        author.current_turn(idx)
        tid = db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (cid, idx, player_input, time.time(), None))
        error = ""
        try:
            for _ in run_pipeline(cid, tid):
                pass
        except Exception as exc:                # noqa: BLE001 - reported
            error = "%s: %s" % (type(exc).__name__, exc)
        played.append({"turn": idx, "input": player_input, "error": error,
                       "turn_id": tid})
    return played


def courier_metrics(db, cid):
    rows = db.q("SELECT s.turn_id, v.content FROM variants v "
                "JOIN steps s ON s.id = v.step_id "
                "WHERE v.active=1 AND s.key='commit' ORDER BY s.turn_id") or []
    out = {}
    for row in rows:
        try:
            results = (json.loads(row["content"]) or {}).get("results") or {}
        except (TypeError, ValueError):
            continue
        out[row["turn_id"]] = results.get("information_carriers") or {}
    return out


def player_saw(author, idx):
    """What the player's own perception payload carried about couriers."""
    for step_key, payload in (author.seen.get(idx) or []):
        if not step_key.startswith("perception"):
            continue
        for perceiver in (payload or {}).get("perceivers") or []:
            if perceiver.get("id") == "player" and perceiver.get("couriers"):
                return perceiver["couriers"]
    return []


def who_knows(db, cid):
    rows = db.q("SELECT ch.name, cc.state FROM chat_chars cc "
                "JOIN characters ch ON ch.id = cc.char_id "
                "WHERE cc.chat_id=?", (cid,)) or []
    out = []
    for row in rows:
        try:
            state = json.loads(row["state"] or "{}")
        except (TypeError, ValueError):
            state = {}
        for report in state.get("carried_reports") or []:
            out.append({"who": row["name"], "claim": report.get("claim"),
                        "provenance": report.get("provenance"),
                        "retellings": report.get("retellings"),
                        "from": report.get("told_by")})
    return out


def run_once(db, intercept):
    author = RoadAuthor()
    import llm_quality

    llm_quality.complete_validated_json = author
    for mod in list(sys.modules.values()):
        if getattr(mod, "complete_validated_json", None) is not None \
                and mod is not llm_quality:
            mod.complete_validated_json = author

    cid = build_story(db)
    played = play(db, cid, author, beats(intercept))
    metrics = courier_metrics(db, cid)

    title = "RUN B — the rider is intercepted" if intercept \
        else "RUN A — the rider gets through"
    print("=" * 66)
    print(title)
    print("=" * 66)
    for row in played:
        print("\nbeat %d  %s" % (row["turn"] + 1, row["input"]))
        if row["error"]:
            print("   ERROR: %s" % row["error"][:120])
            continue
        m = metrics.get(row["turn_id"]) or {}
        fired = []
        if m.get("dispatched"):
            fired.append("courier dispatched")
        if m.get("courier_moves"):
            fired.append("moved %d room(s)" % m["courier_moves"])
        if m.get("courier_delivered"):
            fired.append("DELIVERED")
        if m.get("courier_silenced"):
            fired.append("SILENCED")
        if m.get("courier_questioned"):
            fired.append("questioned")
        if m.get("couriers_standing"):
            fired.append("%d on the road" % m["couriers_standing"])
        if fired:
            print("   engine: %s" % " | ".join(fired))
        saw = player_saw(author, row["turn"])
        for entry in saw:
            print("   Corin's perception: %s -> %s%s"
                  % (entry.get("what"), entry.get("heading"),
                     " (id %s)" % entry.get("courier_id")))
    print("\nwho ended up knowing what:")
    knowledge = who_knows(db, cid)
    if not knowledge:
        print("   nobody learned anything.")
    for item in knowledge:
        print("   %s: %r (%s, %s retelling(s), from %s)"
              % (item["who"], item["claim"], item["provenance"],
                 item["retellings"], item["from"] or "themselves"))
    print()
    return knowledge


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    _require_scratch()
    import db as db_module

    db_module.init()
    delivered = run_once(db_module, intercept=False)
    silenced = run_once(db_module, intercept=True)

    bryn_heard = [k for k in delivered if k["who"] == "Bryn"]
    bryn_spared = [k for k in silenced if k["who"] == "Bryn"]
    print("=" * 66)
    print("verdict: run A Bryn holds %d report(s); run B Bryn holds %d."
          % (len(bryn_heard), len(bryn_spared)))
    ok = bool(bryn_heard) and not bryn_spared
    print("the route %s" % ("WORKED: delivery happened only where the rider "
                            "lived to finish it." if ok else
                            "DID NOT demonstrate the difference."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
