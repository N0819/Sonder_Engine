#!/usr/bin/env python3
"""A caravan and a wanted bill, played through the real pipeline.

The last two carrier legs' honesty test, run as stories rather than as unit
tests, in three runs against fresh chats:

- **RUN A — the caravan**: Bram tells the market crowd what he saw at the
  mill. A trader's caravan sets out empty from the waystation, dwells at the
  market long enough to be robbed (the player stands there watching it), picks
  the talk up, and delivers it in Siege Town three mouths fainter -- count,
  place and name gone, attributed to "a trader's caravan", never to Bram.
- **RUN B — the bill**: Maelor nails up a wanted bill naming an innocent
  (an invented claim -- a lie enters through the same physics as the truth).
  Sera walks up and READS it, and only then knows, with provenance recording
  paper rather than a mouth.
- **RUN C — the bill torn down**: the same posting, but the player rips it
  off the post first. Sera's read is refused and nobody ever learns, which is
  the artifact equivalent of silencing a courier.

Every model output is authored; every mechanism that fires is the engine's
own, including the perception half: the logs show the caravan and the notice
entering the player's OWN perception payload, because robbing a wagon or
tearing down a bill is only real if somebody could see the thing.

Writes only to its own scratch database.

    ENGINE_DB=/path/to/scratch.db python3 tools/caravan_drive.py
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
from tools.story_drive import Author, _base, _blank_diff  # noqa: E402

WAYSTATION, LANE, MARKET, ROAD, TOWN = (
    "waystation", "green_lane", "mill_market", "old_road", "siege_town")

ROOMS = {
    WAYSTATION: ("The Waystation",  "small",  [LANE]),
    LANE:       ("The Green Lane",  "medium", [WAYSTATION, MARKET]),
    MARKET:     ("The Mill Market", "large",  [LANE, ROAD]),
    ROAD:       ("The Old Road",    "large",  [MARKET, TOWN]),
    TOWN:       ("Siege Town",      "large",  [ROAD]),
}

THE_NEWS = "three riders took Maelor's grain at the Mill Market"
THE_LIE = ("the boy from the Fenwater poisoned the "
           "wells of Siege Town")


def scene(positions):
    rooms = {}
    for rid, (name, size, adj) in ROOMS.items():
        rooms[rid] = {"name": name, "size": size,
                      "adjacent": [{"to": t, "barrier": "open"} for t in adj]}
    return {
        "location": "The Vale, eastern reach",
        "time": "morning",
        "rooms": rooms,
        "positions": dict(positions),
        "entities": {},
    }


def build_story(db, positions, *, market_talk=False):
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Corin", json.dumps({
            "name": "Corin",
            "appearance": "A young smith's apprentice on the road east.",
            "senses": "ordinary senses", "abilities": [],
            "public_history": "", "private_history": ""}), "{}"))
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("The Wagon and the Wall", "News moves only when something moves it.",
         time.time(), persona_id))

    for name in [n for n in positions if n != "Corin"]:
        sheet = {"identity": {"name": name, "uid": "%s_uid" % name.lower()},
                 "psychology": {"drive": {"essence": "endure"}}}
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
    if market_talk:
        # The market crowd already carries the story, one mouth on -- the
        # state `apply_tellings` produces when somebody tells a crowd (the
        # path pinned by tests; the Director may not author a registered
        # character's line for the telling, and rightly refuses to). What
        # this drive plays is everything DOWNSTREAM of that state: the
        # pickup, the dwell, the delivery.
        import crowds

        crowd = crowds.new_crowd(cid, MARKET, band="a few dozen",
                                 composition="market traders and mill hands",
                                 since_turn=0, mood="busy")
        import degradation

        crowd = crowds.add_hearsay(crowd, {
            "world_event_id": "event:grain", "source_event_id": "",
            # What the crowd HEARD, not what happened: stored already one
            # mouth faint, exactly as apply_tellings stores it.
            "claim": degradation.degrade(THE_NEWS, 1),
            "kind": "consequence", "occurred_at": 10.0,
            "acquired_turn": 0, "retellings": 1, "told_by": "a mill hand",
            "provenance": "told"})
        db.wset(cid, "crowds", [crowd])
    db.wset(cid, "scene", scene(positions))
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    db.wset(cid, "living_world", {"rumor_ledger": "floor"})
    return cid


class Vale(Author):
    """Authors the opening, and keeps every payload it was shown."""

    def __init__(self, positions):
        super().__init__()
        self.positions = positions
        self.seen = {}

    def __call__(self, *, role, step_key, system, payload, **kw):
        self.seen.setdefault(getattr(self, "_turn", -1), []).append(
            (step_key, payload))
        return super().__call__(role=role, step_key=step_key, system=system,
                                payload=payload, **kw)

    def default(self, role):
        if role == "director_establish":
            world = scene(self.positions)
            out = _base("director_establish")
            out["location"] = world["location"]
            out["time"] = world["time"]
            out["scene_description"] = "The vale road, market and town."
            out["rooms"] = {
                rid: {"name": r["name"], "adjacent": r["adjacent"],
                      "size": r["size"]}
                for rid, r in world["rooms"].items()}
            out["positions"] = dict(world["positions"])
            out["entities"] = {}
            return out
        return super().default(role)


def make_R():
    """A resolve-payload factory over a cumulative clock (see courier_drive
    for why the clock must be absolute, not per-beat deltas)."""
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
    return R


def dynamic(prebuilt, fill):
    """A resolve beat whose ops need an engine-minted id from the payload."""
    def beat(p):
        out = copy.deepcopy(prebuilt)
        fill(out, p or {})
        return out
    beat.prose = prebuilt["resolved_event"]
    return beat


def caravan_beats():
    """RUN A's script: the market's talk boards a wagon and rides east.

    The crowd already holds the story one mouth on (seeded in build_story;
    that state is `apply_tellings`' and is pinned by tests). What this run
    plays is the deferred feature itself: the wagon dwelling in the market,
    picking the talk up, and delivering it two more mouths fainter in a
    town the player watched it leave for -- and could have followed.
    """
    R = make_R()

    return [
        # Beat 1 is the opening turn: it runs director_establish, never a
        # resolve, so nothing may be declared on it (the courier_drive
        # lesson, relearned the played way).
        ("I come into the market with the morning crowd.",
         R("The Mill Market opens under a clear sky.")),
        ("I buy bread and keep watching the lane.",
         R("A trader's caravan forms up at the waystation and creaks "
           "east toward the market.", seconds=60,
           diff={"courier_ops": [{
               "op": "send", "to_room": TOWN, "stops": [MARKET],
               "from_room": WAYSTATION, "pace": "walking",
               "description": "a trader's caravan"}]})),
        ("I wait and watch the wagons come in.",
         R("The caravan rolls into the market and halts among the stalls.",
           seconds=1200)),
        ("I walk a slow circle around the halted wagons.",
         R("The traders water their mules and talk with the crowd. The "
           "wagons stand within arm's reach.", seconds=600)),
        ("I let them go and stay in the market.",
         R("The caravan creaks out east; the road takes it toward Siege "
           "Town.", seconds=3600)),
    ]


def bill_beats(torn_down):
    """RUN B/C's script: a claim is nailed to a wall, and read or destroyed.

    Prebuilt beats are created IN SCRIPT ORDER, because make_R's clock is
    cumulative -- a prebuilt minted early carries an early clock and the
    beat then reads as time running backwards (courier_drive's lesson).
    """
    R = make_R()

    def read_fill(out, p):
        notices = p.get("notices") or []
        if notices:
            out["state_diff"]["artifact_ops"] = [{
                "op": "read", "reader": "Sera",
                "artifact_id": notices[0].get("artifact_id")}]

    def tear_fill(out, p):
        notices = p.get("notices") or []
        if notices:
            out["state_diff"]["artifact_ops"] = [{
                "op": "remove", "by": "Corin", "manner": "torn down",
                "artifact_id": notices[0].get("artifact_id")}]

    B = [
        # Opening turn: establish only, declare nothing (see caravan_beats).
        ("I come into the market square.",
         R("The market square, the well, and the notice post.")),
        ("I cross the square toward the well.",
         R("Maelor nails a fresh bill to the post by the well.",
           diff={"artifact_ops": [{
               "op": "post", "poster": "Maelor", "claim": THE_LIE,
               "description": "a wanted bill with a clumsy woodcut"}]})),
    ]
    if torn_down:
        B += [("I tear the bill off the post before anyone reads it.",
               dynamic(R("Corin rips the bill from the post and crushes it "
                         "into the mud.", seconds=30), tear_fill))]
    B += [
        ("I watch who stops at the post.",
         dynamic(R("Sera stops before the post and looks it over.",
                   seconds=60), read_fill)),
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


def commit_metrics(db, cid):
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


def player_saw(author, idx, key):
    """What the player's own perception payload carried under one key."""
    for step_key, payload in (author.seen.get(idx) or []):
        if not step_key.startswith("perception"):
            continue
        for perceiver in (payload or {}).get("perceivers") or []:
            if perceiver.get("id") == "player" and perceiver.get(key):
                return perceiver[key]
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


def hook_author(author):
    import llm_quality

    llm_quality.complete_validated_json = author
    for mod in list(sys.modules.values()):
        if getattr(mod, "complete_validated_json", None) is not None \
                and mod is not llm_quality:
            mod.complete_validated_json = author


def print_beats(title, played, metrics, author, db, cid):
    print("=" * 66)
    print(title)
    print("=" * 66)
    for row in played:
        print("\nbeat %d  %s" % (row["turn"] + 1, row["input"]))
        if row["error"]:
            print("   ERROR: %s" % row["error"][:160])
            continue
        m = metrics.get(row["turn_id"]) or {}
        fired = []
        for key, label in (
                ("told", "telling applied"),
                ("dispatched", "caravan dispatched"),
                ("courier_moves", "moved %d room(s)"),
                ("caravan_stops", "dwelt at %d stop(s)"),
                ("caravan_picked_up", "picked up %d report(s)"),
                ("caravan_put_down", "told the crowd %d report(s)"),
                ("courier_delivered", "DELIVERED"),
                ("courier_silenced", "SILENCED"),
                ("artifacts_posted", "bill POSTED"),
                ("artifacts_read", "bill READ"),
                ("artifacts_removed", "bill TORN DOWN"),
                ("artifact_rejected", "%d artifact op(s) REFUSED"),
                ("couriers_standing", "%d on the road")):
            value = m.get(key)
            if value:
                fired.append(label % value if "%d" in label else label)
        if fired:
            print("   engine: %s" % " | ".join(fired))
        for entry in player_saw(author, row["turn"], "couriers"):
            print("   Corin's perception: %s -> %s%s"
                  % (entry.get("what"), entry.get("heading"),
                     " (id %s)" % entry.get("courier_id")))
        for entry in player_saw(author, row["turn"], "notices"):
            print("   Corin's perception: %s (id %s)"
                  % (entry.get("what"), entry.get("artifact_id")))
    print("\nwho ended up knowing what:")
    knowledge = [k for k in who_knows(db, cid)
                 if k["provenance"] != "witnessed_surface"]
    if not knowledge:
        print("   nobody learned anything.")
    for item in knowledge:
        print("   %s: %r (%s, %s retelling(s), from %s)"
              % (item["who"], item["claim"], item["provenance"],
                 item["retellings"], item["from"] or "themselves"))
    print()
    return knowledge


def run_caravan(db):
    positions = {"Corin": MARKET, "Tessa": TOWN}
    author = Vale(positions)
    hook_author(author)
    cid = build_story(db, positions, market_talk=True)
    played = play(db, cid, author, caravan_beats())
    return print_beats("RUN A — the caravan carries the market's talk east",
                       played, commit_metrics(db, cid), author, db, cid)


def run_bill(db, torn_down):
    positions = {"Corin": MARKET, "Maelor": MARKET, "Sera": MARKET}
    author = Vale(positions)
    hook_author(author)
    cid = build_story(db, positions)
    played = play(db, cid, author, bill_beats(torn_down))
    title = ("RUN C — the bill is torn down first, and nobody learns"
             if torn_down else
             "RUN B — a wanted bill is read off the post")
    return print_beats(title, played, commit_metrics(db, cid), author, db, cid)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    _require_scratch()
    import db as db_module

    db_module.init()
    carried = run_caravan(db_module)
    read = run_bill(db_module, torn_down=False)
    spared = run_bill(db_module, torn_down=True)

    tessa = [k for k in carried if k["who"] == "Tessa"]
    sera_read = [k for k in read if k["who"] == "Sera"]
    sera_spared = [k for k in spared if k["who"] == "Sera"]
    print("=" * 66)
    print("verdict:")
    print("  run A: Tessa holds %d report(s); degraded and anonymous: %s"
          % (len(tessa),
             bool(tessa) and tessa[0]["retellings"] >= 2
             and "three" not in (tessa[0]["claim"] or "")
             and tessa[0]["from"] == "a trader's caravan"))
    print("  run B: Sera holds %d report(s) with provenance %s"
          % (len(sera_read),
             sera_read[0]["provenance"] if sera_read else "-"))
    print("  run C: Sera holds %d report(s) after the bill came down"
          % len(sera_spared))
    ok = (bool(tessa) and tessa[0]["retellings"] >= 2
          and "three" not in (tessa[0]["claim"] or "")
          and bool(sera_read) and sera_read[0]["provenance"] == "read"
          and not sera_spared)
    print("the network %s" % (
        "WORKED: news moved only where something carried it, and stopped "
        "where a hand stopped it." if ok else
        "DID NOT demonstrate the difference."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
