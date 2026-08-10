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
                 {"id": away_id, "sheet": away_sheet}]


def make_ctx(cid, cast, turn_idx, db, *, resolve=None):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, turn_idx, "", time.time()))
    return _Ctx(
        chat=_Chat(id=cid),
        turn=types.SimpleNamespace(id=turn_id, idx=turn_idx, frame_id=None),
        cast=cast, character_results={}, director_resolve=resolve or {},
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
                    "witnessed": "the gate was barred from the inside",
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
    warned = [w for b in report["beats"] for w in b["warnings"]]
    if warned:
        print("\n  warnings:")
        for w in warned[:10]:
            print(f"    {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
