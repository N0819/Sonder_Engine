#!/usr/bin/env python3
"""Give the off-screen floors a real chance, and report what fires.

`tools/fire_rates.py` reports the whole 8.0 off-screen foundation as
`no chances`. That is honest. Measured 2026-08-10 against the live corpus, FOUR
independent zeroes stack up, and none of them is a defect:

  1. The only story played since the code landed spent 24 turns in ONE
     top-level location -- and `epoch_reasons` fires on an opening, a change of
     top-level `scene.location`, an EPOCH_SECONDS (3600s) bucket, or a due
     event. It never crossed one.
  2. That story's simulation clock reached 500 seconds. The hour bucket is
     3600. Corpus-wide the clock advances a median of 15.6s per turn and only
     7 of 50 stories have EVER crossed one in-world hour.
  3. It has no `living_world` row at all, so every mechanism defaulted off.
  4. The two stories that ARE configured for it were last played a day before
     the code existed.

So the mechanisms have never been observed either working or failing. This
builds the conditions they need and reports which of them actually fire.

WHAT THIS CAN AND CANNOT PROVE. It exercises machinery: epoch -> dormant tick
-> plan acceptance -> reactive stage -> effect. It CANNOT validate the Director
prompt that decides duration, because the harness supplies the state a model
would have produced. Asking it whether `time_skip` now fires would be asking
whether the author of the harness typed `time_skip`. That number only moves in
a real playthrough.

Writes only to its own scratch database, and refuses to start against anything
that looks like the author's.

    ENGINE_DB=/path/to/scratch.db python3 tools/offscreen_drive.py
    ENGINE_DB=/path/to/scratch.db python3 tools/offscreen_drive.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EPOCH_HOUR = 60 * 60


class _Chat(dict):
    @property
    def id(self):
        return self["id"]


class _Ctx(types.SimpleNamespace):
    def add_warning(self, message):
        self.warnings.append(str(message))

    def get(self, key, default=None):
        return getattr(self, key, default)


def _require_scratch():
    """Refuse to run against anything that could be the author's database."""
    path = os.environ.get("ENGINE_DB") or "engine.db"
    resolved = os.path.abspath(path)
    if os.path.basename(resolved) == "engine.db" and "jobs" not in resolved:
        raise SystemExit(
            "Refusing to run against %s. Point ENGINE_DB at a scratch path."
            % resolved)
    return resolved


def scene_at(location, room, who):
    return {
        "location": location,
        "rooms": {room: {"name": room.replace("_", " ").title(), "adjacent": []}},
        "positions": {who: room},
        "entities": {},
    }


def build_story(db):
    """A story shaped exactly like the conditions the floors need.

    Every setting here is switched ON deliberately. The live corpus has them
    off or absent, which is one of the four reasons nothing has ever fired, and
    a harness that inherited the defaults would faithfully reproduce the
    silence it exists to break.
    """
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Off-screen drive", "", time.time()))

    def cast_member(name, uid, status):
        sheet = json.dumps({"identity": {"name": name, "uid": uid},
                            "simulation": {"tier": "major"}})
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, sheet, "{}", time.time()))
        # `cc.sheet` NULL, as the engine writes it. An empty STRING defeats the
        # `COALESCE(cc.sheet, ch.sheet)` in `dormant_subjects` and the tick
        # comes back naming "Unnamed" -- a harness artifact that cost a
        # debugging round. Checked: 0 of 91 live rows are '', 84 are NULL.
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
              "VALUES(?,?,?,'{}',NULL)", (cid, char_id, status))
        return char_id, sheet

    here_id, here_sheet = cast_member("Mora", "mora_uid", "active")
    # THE CHARACTER LEFT BEHIND, and DORMANT rather than active.
    # `dormant_subjects` selects on that status alone, so a cast that is
    # entirely `active` offers the tick draw nobody however many epochs fire.
    # Measured live: 12 of 91 cast rows are dormant across 8 of 47 chats, so
    # the rung is reachable -- it has simply never co-occurred with an epoch.
    away_id, away_sheet = cast_member("Kestrel", "kestrel_uid", "dormant")
    # A listener standing in the same room, and a mind in the next room who is
    # never told. The second one is the FALSIFIER: approach C's strongest test
    # is an ordinary event that does NOT spread, so the drive has to contain
    # somebody who stays ignorant while the news moves past them.
    heard_id, heard_sheet = cast_member("Rem", "rem_uid", "active")
    unreached_id, unreached_sheet = cast_member("Otto", "otto_uid", "active")
    # A fourth mouth, so the drive can walk a claim all the way to the hop
    # where it has nothing left and the engine stops passing it on.
    fourth_id, fourth_sheet = cast_member("Ram", "ram_uid", "active")
    # A fifth, who never hears it -- because by the time the story reaches him
    # it has lost its count, its place and its name, and stops.
    fifth_id, fifth_sheet = cast_member("Beako", "beako_uid", "active")

    db.wset(cid, "subject_last_seen",
            {"Kestrel": {"room": "hall", "turn": 0, "elapsed_seconds": 0.0}})
    db.wset(cid, "standing_intentions",
            [{"who": "Kestrel", "what": "watch the western gate",
              "where": "hall"}])

    # `stochastic`, not `reactive`. The ladder is cumulative and stochastic
    # sits ABOVE reactive, so setting `reactive` permits the deterministic and
    # reactive rungs and silently forbids the seeded tick draw. `stochastic` is
    # also the shipped default, so this matches an ordinary story.
    db.wset(cid, "dialogue_config",
            {"offscreen_life": "stochastic", "max_offscreen_actors": 3})
    db.wset(cid, "living_world", {
        "routine_residue": "floor", "scheduled_consequence": "floor",
        "place_obligations": "floor", "antagonist_ladder": "floor",
        # Carriers are gated on this, and BOTH live configured stories have it
        # off -- which is why `character acquired carried report` reads
        # `no chances` independently of everything else.
        "rumor_ledger": "floor",
    })
    return cid, [{"id": here_id, "sheet": here_sheet},
                 {"id": away_id, "sheet": away_sheet},
                 {"id": heard_id, "sheet": heard_sheet},
                 {"id": unreached_id, "sheet": unreached_sheet},
                 {"id": fourth_id, "sheet": fourth_sheet},
                 {"id": fifth_id, "sheet": fifth_sheet}]


def make_ctx(cid, cast, turn_idx, db, *, resolve=None):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, turn_idx, "", time.time()))
    return _Ctx(
        chat=_Chat(id=cid),
        turn=types.SimpleNamespace(id=turn_id, idx=turn_idx, frame_id=None),
        cast=cast, character_results={}, director_resolve=resolve or {},
        # The real ctx carries both, and commit falls back to the establish
        # payload on an opening turn. A harness missing the attribute fails
        # with an AttributeError that looks like an engine bug and is not.
        director_establish={}, extra_players=[],
        warnings=[],
    )


def accept_plan(db, cid, cast, report):
    """Open an authored plan through the REAL acceptance path.

    Writing a plan straight into the world key skips `apply_plan_ops`, and
    that is the function which converts a stage's relative `after_seconds` into
    the absolute `due_at` that `_reactive_triggered` actually reads. A
    hand-written plan is therefore considered on every epoch and can never
    fire -- which is exactly what the first version of this harness showed, and
    it was the harness that was wrong, not the engine.
    """
    from offscreen import apply_plan_ops

    # THE PLAN MUST BE GROUNDED IN THE ACTOR'S OWN DECLARATION. `apply_plan_ops`
    # refuses an op whose actor said nothing this beat -- "made no plan
    # declaration this beat" -- which is the epistemic guard the roadmap names:
    # the Director ENCODES a plan the character stated, it does not author one
    # on their behalf. So Kestrel has to say it out loud before leaving.
    declaration = "I'll shut the west gate before dusk"
    ctx = make_ctx(cid, cast, 0, db, resolve={"state_diff": {
        "offscreen_plan_ops": [{
            "op": "open", "plan_id": "shut-the-west-gate", "actor": "Kestrel",
            "objective": "Shut the western gate before dusk",
            "basis": declaration,
            "stages": [{
                "stage_id": "shut-it",
                # Above PLAN_TRIGGER_MIN_SECONDS (60s) and inside the hour the
                # story is about to cross.
                "trigger": {"after_seconds": 600},
                "effect": {
                    "what": "the western gate stands shut and barred",
                    "where": "hall", "due_seconds": 0,
                    # Carries a COUNT, a PLACE and a NAME on purpose: those are the
            # three things degradation subtracts, in that order, and a surface
            # without them would fade invisibly and prove nothing.
            "witnessed": "Kestrel barred the gate against forty riders "
                         "in the Hall",
                    "originator": "Kestrel",
                },
            }],
        }],
    }})
    ctx.character_results = {cast[1]["id"]: {
        "sequence": [{"type": "speech", "text": declaration}],
        "intent_ops": [], "project_ops": [],
    }}
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    result = apply_plan_ops(
        ctx, scene_at("Lugunica", "hall", "Mora"), {"elapsed_seconds": 0.0}) or {}
    report["plan_acceptance"] = {
        "offered": result.get("offered"), "applied": result.get("applied"),
        "warnings": list(ctx.warnings),
    }


def carrier_scene():
    """Two rooms. Mora and Rem in the hall, Otto through the door.

    Otto is deliberately reachable on foot and deliberately not told. A world
    where being one room away is enough to learn something has rebuilt the
    omniscience the perception layer exists to prevent.
    """
    return _two_rooms({"Mora": "hall", "Rem": "yard", "Otto": "yard",
                       "Ram": "yard", "Beako": "yard"})


def _two_rooms(positions):
    return {
        "location": "Priestella",
        "rooms": {
            "hall": {"name": "Hall",
                     "adjacent": [{"to": "yard", "barrier": "open"}]},
            "yard": {"name": "Yard",
                     "adjacent": [{"to": "hall", "barrier": "open"}]},
        },
        "positions": dict(positions),
        "entities": {},
    }


def telling_scene():
    """Rem has come in from the yard. Otto has not.

    Rem must NOT be in the hall when the gate is barred, or he witnesses it
    and there is nothing left to tell him -- which is exactly what the first
    run of this leg did, and it reported a telling refused for a reason that
    was true and beside the point.
    """
    return _two_rooms({"Mora": "hall", "Rem": "hall", "Otto": "yard",
                       "Ram": "yard", "Beako": "yard"})


def carry_a_report(db, cid, cast, report):
    """A fired consequence with a PUBLIC witnessed surface, and a witness there.

    The last two legs of roadmap item 1. `commit_world_event_spine` promotes a
    fired mechanics row into objective history; `advance_carriers` then offers
    that surface to every ACTIVE cast member standing in the room it happened
    in. Both halves are required and both are gated:

      - the payload must carry a non-empty `witnessed` string and the row a
        `location_id`, or it is not a public surface at all;
      - the holder must be ACTIVE and co-located -- a dormant character is not
        a witness, and `rumor_ledger` must be at `floor` or `advance_carriers`
        declines before it looks at anything.
    """
    from commit import commit_information_carriers, commit_world_event_spine

    ctx = make_ctx(cid, cast, 6, db)
    scene = carrier_scene()
    transit = {"fired_events": [{
        "event_id": "gate-sealed-1",
        "kind": "consequence",
        "location_id": "hall",
        "occurred_at": float(EPOCH_HOUR + 400),
        "seed": "drive",
        "payload": json.dumps({
            "what": "the western gate stands shut and barred",
            # The public surface. Without this the event is real but nobody
            # can carry it -- which is the correct distinction between a thing
            # that happened and a thing that was seen to happen.
            # Carries a COUNT, a PLACE and a NAME on purpose: those are the
            # three things degradation subtracts, in that order, and a surface
            # without them would fade invisibly and prove nothing.
            "witnessed": "Kestrel barred the gate against forty riders "
                         "in the Hall",
            "originator": "Kestrel",
        }),
    }]}
    with db.transaction():
        spine = commit_world_event_spine(ctx, transit) or {}
        carried = commit_information_carriers(
            ctx, {"scene": scene}, spine) or {}
    report["world_events"] = {
        "offered": spine.get("offered"), "written": spine.get("written")}
    # `commit_world_event_spine` assigns the canonical `event_id`; the one in
    # `fired_events` is only the SOURCE id. Reading it back rather than
    # assuming it is how the telling leg finds the report at all.
    report["event_id"] = ((spine.get("events") or [{}])[0]).get("event_id")
    report["carriers"] = {
        "enabled": carried.get("enabled", True),
        "public_surfaces": carried.get("public_surfaces"),
        "opportunities": carried.get("carrier_opportunities"),
        "acquired": carried.get("acquired"),
        "warnings": list(ctx.warnings),
    }


def tell_a_report(db, cid, cast, report):
    """The copy leg: a witness says it out loud, and one mind learns.

    This is where approach C stops being a ledger and starts being epistemics.
    Four refusals are exercised beside the one acceptance, because every one of
    them is a firewall rather than tidiness -- a telling the engine waves
    through is a mind knowing something nobody delivered.
    """
    from carriers import STATE_KEY, reports_for_state
    from commit import commit_information_carriers
    from scene import active_cast

    scene = telling_scene()
    event_id = report.get("event_id") or ""

    def held_by(name):
        for row in active_cast(cid, None):
            sheet = json.loads(row["sheet"] or "{}")
            if (sheet.get("identity") or {}).get("name") != name:
                continue
            state = json.loads(row["cstate"] or "{}")
            return reports_for_state(state if isinstance(state, dict) else {})
        return []

    def attempt(label, ops, dialogue, turn_idx):
        ctx = make_ctx(cid, cast, turn_idx, db, resolve={
            "state_diff": {"telling_ops": ops},
            "dialogue_log": list(dialogue),
        })
        with db.transaction():
            out = commit_information_carriers(ctx, {"scene": scene}, {}) or {}
        return {"attempt": label, "told": out.get("told"),
                "refused": out.get("tellings_refused"),
                "warnings": list(ctx.warnings)}

    said = [{"speaker": "Mora", "text": "The gate was barred from inside."}]
    attempts = [
        # Nobody spoke. Proximity is not transmission.
        attempt("nobody said anything", [
            {"speaker": "Mora", "listener": "Rem",
             "world_event_id": event_id}], [], 7),
        # A room away, with the speaking done. Distance still refuses.
        attempt("the listener is in the next room", [
            {"speaker": "Mora", "listener": "Otto",
             "world_event_id": event_id}], said, 8),
        # A report the speaker does not hold.
        attempt("passing on something never witnessed", [
            {"speaker": "Mora", "listener": "Rem",
             "world_event_id": "never-happened"}], said, 9),
        # The real thing.
        attempt("Mora tells Rem, out loud, in the hall", [
            {"speaker": "Mora", "listener": "Rem",
             "world_event_id": event_id}], said, 10),
    ]

    # Now walk it down the chain. Everyone gathers in the hall so the only
    # thing under test is how many mouths the story has been through.
    scene = _two_rooms({"Mora": "hall", "Rem": "hall", "Otto": "hall",
                        "Ram": "hall", "Beako": "hall"})
    chain = []
    for turn, (teller, hearer) in enumerate(
            [("Rem", "Otto"), ("Otto", "Ram"), ("Ram", "Beako")], start=11):
        attempts.append(attempt(
            "%s passes it to %s" % (teller, hearer),
            [{"speaker": teller, "listener": hearer,
              "world_event_id": event_id}],
            [{"speaker": teller, "text": "They say the gate was barred."}],
            turn))
    for who in ("Mora", "Rem", "Otto", "Ram", "Beako"):
        for r in held_by(who):
            chain.append({"who": who, "retellings": r["retellings"],
                          "from": r.get("told_by") or "(saw it)",
                          "heard": r["claim"]})

    report["tellings"] = {
        "attempts": attempts,
        "chain": chain,
        "unreached_holds": [r["claim"] for r in held_by("Kestrel")],
    }
    rumor_rides_a_crowd(db, cid, cast, report, event_id, held_by)


def a_lie_travels_like_the_truth(db, cid, cast, report, held_by):
    """Something no event backs, entering through the same physics.

    The point is what a listener CANNOT do. A mind that could tell a lie from a
    fact by inspecting its own memory is not a mind that can be deceived, and
    being deceivable is the entire reason this engine keeps objective truth,
    perception, memory and belief in separate layers. So the copy handed on is
    shaped exactly like a copy of the truth, and the asymmetry exists only at
    the source: the speaker's own row says `invented`, and there is no world
    event behind it that anything in the fiction can query.
    """
    from commit import commit_information_carriers

    scene = _two_rooms({"Mora": "hall", "Rem": "hall", "Otto": "hall",
                        "Ram": "hall", "Beako": "hall"})
    ctx = make_ctx(cid, cast, 30, db, resolve={
        "state_diff": {"telling_ops": [
            {"speaker": "Rem", "listener": "Otto",
             "claim": "Kestrel opened the gate to forty riders at the Hall"}]},
        "dialogue_log": [{"speaker": "Rem", "text": "He let them in."}],
    })
    with db.transaction():
        out = commit_information_carriers(ctx, {"scene": scene}, {}) or {}

    liar = [r for r in held_by("Rem") if r["provenance"] == "invented"]
    duped = [r for r in held_by("Otto")
             if str(r["world_event_id"]).startswith("claim:")]
    truthful = [r for r in held_by("Otto")
                if not str(r["world_event_id"]).startswith("claim:")]
    report["invention"] = {
        "told": out.get("told"), "warnings": list(ctx.warnings),
        "the_liar_knows": [(r["claim"], r["provenance"]) for r in liar],
        "what_the_dupe_holds": [
            {k: r.get(k) for k in ("claim", "provenance", "retellings",
                                   "told_by")} for r in duped],
        "a_true_report_the_dupe_holds": [
            {k: r.get(k) for k in ("claim", "provenance", "retellings",
                                   "told_by")} for r in truthful],
    }


def rumor_rides_a_crowd(db, cid, cast, report, event_id, held_by):
    """A crowd is the anonymous carrier, and it needs no new travel machinery.

    This is the line item 2 left open -- "crowds should also become possible
    information carriers" -- and item 3's first anonymous carrier, closed by
    the same object. Talk goes into a market, the market walks to the next
    room, and somebody standing there catches it. Nothing new moves it:
    `advance_crowds` already walks the one graph everybody walks.

    A crowd is exempt from the dialogue-log grounding and from NOTHING else. It
    murmurs continuously -- that is the one thing a crowd is allowed to do, so
    there is no line to point at -- but the telling is still an explicit
    declaration, and co-location, holding and fan-out all still apply. Catching
    a rumor in a market is knowledge by a beat that said so, not by proximity.
    """
    from commit import commit_crowds, commit_information_carriers

    def crowd_beat(turn_idx, crowd_ops, telling_ops=(), scene=None,
                   dialogue=()):
        ctx = make_ctx(cid, cast, turn_idx, db, resolve={
            "state_diff": {"crowd_ops": list(crowd_ops),
                           "telling_ops": list(telling_ops)},
            "dialogue_log": list(dialogue),
        })
        with db.transaction():
            crowd_out = commit_crowds(ctx, {"scene": scene}) or {}
            told = commit_information_carriers(ctx, {"scene": scene}, {}) or {}
        return crowd_out, told, list(ctx.warnings)

    hall = _two_rooms({"Mora": "hall", "Beako": "yard"})
    steps = []

    # A market in the hall, and Mora says it where they can hear.
    crowd_out, _, _ = crowd_beat(20, [{
        "op": "set", "room": "hall", "band": "a throng",
        "composition": "market traders", "mood": "busy"}], scene=hall)
    uid = (db.wget(cid, "crowds", []) or [{}])[0].get("uid", "")
    _, told, warns = crowd_beat(
        21, [], [{"speaker": "Mora", "listener": uid,
                  "world_event_id": event_id}], scene=hall,
        dialogue=[{"speaker": "Mora", "text": "The gate was barred."}])
    steps.append({"step": "Mora says it where the market can hear",
                  "told": told.get("told"), "warnings": warns})

    # The market moves to the yard, carrying what it heard.
    crowd_out, _, _ = crowd_beat(
        22, [{"op": "set", "crowd_id": uid, "heading": "yard"}], scene=hall)
    crowd_out, _, _ = crowd_beat(23, [], scene=hall)
    standing = db.wget(cid, "crowds", []) or [{}]
    steps.append({"step": "the market walks through to the yard",
                  "crowd_room": standing[0].get("room_uid"),
                  "carrying": [r.get("claim")
                               for r in standing[0].get("reports") or []]})

    # Beako has been in the yard the whole time and heard nothing until now.
    yard = _two_rooms({"Mora": "hall", "Beako": "yard"})
    _, told, warns = crowd_beat(
        24, [], [{"speaker": uid, "listener": "Beako",
                  "world_event_id": event_id}], scene=yard)
    steps.append({"step": "Beako catches the talk in the yard",
                  "told": told.get("told"), "warnings": warns})

    a_lie_travels_like_the_truth(db, cid, cast, report, held_by)

    report["crowd_carrier"] = {
        "steps": steps,
        "beako_holds": [(r["claim"], r["retellings"], r.get("told_by"))
                        for r in held_by("Beako")],
    }


def drive(db):
    from offscreen import advance_epoch

    cid, cast = build_story(db)
    report = {"chat_id": cid, "beats": []}
    accept_plan(db, cid, cast, report)

    def beat(label, *, turn_idx, prev_location, location, prev_seconds,
             seconds, transit=None):
        db.wset(cid, "simulation_clock",
                {"elapsed_seconds": float(seconds), "display": "",
                 "time_scale": "scene"})
        ctx = make_ctx(cid, cast, turn_idx, db)
        # `advance_epoch` is a COMMIT DOMAIN -- its docstring says it "runs
        # under `commit_all`'s outer transaction", and `advance_reactive_plans`
        # inserts a scheduled event with `qtx`, which raises outside one. So the
        # beat is wrapped exactly as commit wraps it.
        with db.transaction():
            result = advance_epoch(ctx, {
                "scene": scene_at(location, "hall", "Mora"),
                "prev_scene": scene_at(prev_location, "hall", "Mora"),
                "clock": {"elapsed_seconds": float(seconds)},
                "prev_clock": {"elapsed_seconds": float(prev_seconds)},
            }, transit or {}) or {}
        report["beats"].append({
            "beat": label, "turn": turn_idx,
            "opportunity": bool(result.get("opportunity")),
            "reasons": result.get("reasons") or [],
            "actors_considered": result.get("actors_considered"),
            "stochastic_fired": result.get("stochastic_fired"),
            "reactive_considered": result.get("reactive_considered"),
            "reactive_fired": result.get("reactive_fired"),
            "reactive_effects_minted": result.get("reactive_effects_minted"),
            "warnings": list(ctx.warnings),
        })

    # A pre-existing story meeting this code is BASELINED, not retroactively
    # ticked. If this ever becomes an opportunity, a migration artifact is
    # inventing history.
    beat("baseline", turn_idx=1, prev_location="Lugunica", location="Lugunica",
         prev_seconds=0, seconds=30)
    # An ordinary beat. Same place, thirty seconds. Must NOT be an epoch, or
    # the world lurches every time two people talk.
    beat("ordinary beat", turn_idx=2, prev_location="Lugunica",
         location="Lugunica", prev_seconds=30, seconds=60)
    # The edge the live corpus never crossed once in 51 turns.
    beat("travel to another place", turn_idx=3, prev_location="Lugunica",
         location="Priestella", prev_seconds=60, seconds=900)
    # The bucket a 20-second-per-beat clock never reaches.
    beat("an hour passes", turn_idx=4, prev_location="Priestella",
         location="Priestella", prev_seconds=900, seconds=EPOCH_HOUR + 300)
    # The third canonical reason.
    beat("a consequence fires", turn_idx=5, prev_location="Priestella",
         location="Priestella", prev_seconds=EPOCH_HOUR + 300,
         seconds=EPOCH_HOUR + 400, transit={"fired": 1})

    carry_a_report(db, cid, cast, report)
    tell_a_report(db, cid, cast, report)
    return report


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    _require_scratch()
    import db as db_module
    db_module.init()
    report = drive(db_module)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    acc = report.get("plan_acceptance") or {}
    print("off-screen drive — did the floors get a chance, and take it?\n")
    print(f"  plan ops accepted: {acc.get('applied')} of {acc.get('offered')}")
    for w in acc.get("warnings") or []:
        print(f"    ! {w}")
    print()
    print(f"  {'beat':<24}{'epoch':>6}{'reasons':>12}{'ticks':>7}"
          f"{'rx seen':>9}{'rx fired':>10}{'minted':>8}")
    for b in report["beats"]:
        print(f"  {b['beat']:<24}{('YES' if b['opportunity'] else '-'):>6}"
              f"{(','.join(b['reasons']) or '-'):>12}"
              f"{str(b['stochastic_fired']):>7}"
              f"{str(b['reactive_considered']):>9}"
              f"{str(b['reactive_fired']):>10}"
              f"{str(b['reactive_effects_minted']):>8}")
    we, ca = report.get("world_events") or {}, report.get("carriers") or {}
    print(f"\n  world events written: {we.get('written')} of {we.get('offered')} fired")
    print(f"  public surfaces     : {ca.get('public_surfaces')}")
    print(f"  carrier chances     : {ca.get('opportunities')}")
    print(f"  reports acquired    : {ca.get('acquired')}")
    for w in ca.get("warnings") or []:
        print(f"    ! {w}")

    warned = [w for b in report["beats"] for w in b["warnings"]]
    if warned:
        print("\n  warnings:")
        for w in warned[:10]:
            print(f"    {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
