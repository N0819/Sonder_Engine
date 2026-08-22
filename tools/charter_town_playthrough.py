#!/usr/bin/env python3
"""Interactive thirty-turn Charter town playtest on an isolated DB copy.

This is the model-driven counterpart to the pure Charter fixtures.  Only the
opening world is authored: every turn after that runs through the production
Director, perception, Scene Life, character, narrator, and commit pipeline.
The operator supplies one ordinary player input at each ``INPUT>`` prompt and
sees the exact narrator output before choosing the next.

The source database is copied only to inherit configured providers/settings.
The copy lives in a temporary directory and is deleted; the transcript and a
sanitized turn/audit JSON are the only retained artefacts.

    python3 tools/charter_town_playthrough.py \
        --source engine.db --out demos/charter-town-playtest-2026-08-21
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


PLAYER = "Rowan Hale"
ROOMS = {
    "north_gate": {
        "name": "North Gate",
        "size": "large",
        "desc": "A slate-roofed gatehouse where the upland road enters town.",
        "adjacent": ["market_square"],
    },
    "market_square": {
        "name": "Market Square",
        "size": "huge",
        "desc": "A cobbled square of striped awnings, handcarts, and a dry fountain.",
        "adjacent": ["north_gate", "council_hall", "well_house",
                     "bakehouse", "riverside", "wayfarers_inn"],
    },
    "council_hall": {
        "name": "Council Hall",
        "size": "medium",
        "desc": "An old wool hall repurposed for ledgers, petitions, and argument.",
        "adjacent": ["market_square"],
    },
    "well_house": {
        "name": "Well House",
        "size": "small",
        "desc": "A cool stone chamber around the town's deep chain-pump well.",
        "adjacent": ["market_square"],
    },
    "bakehouse": {
        "name": "Common Bakehouse",
        "size": "medium",
        "desc": "Two communal ovens under a soot-dark vault, warm with old rye.",
        "adjacent": ["market_square"],
    },
    "riverside": {
        "name": "Riverside Steps",
        "size": "large",
        "desc": "Broad worn steps descend to the millstream and the timber bridge.",
        "adjacent": ["market_square", "mill", "infirmary"],
    },
    "mill": {
        "name": "Greywater Mill",
        "size": "large",
        "desc": "A low riverside mill whose wheel turns beneath a flour-pale gallery.",
        "adjacent": ["riverside"],
    },
    "infirmary": {
        "name": "Saint Orra's Infirmary",
        "size": "medium",
        "desc": "A clean limewashed house with six cots and a bitter-herb garden.",
        "adjacent": ["riverside"],
    },
    "wayfarers_inn": {
        "name": "Wayfarer's Rest",
        "size": "large",
        "desc": "A deep-beamed inn overlooking the square, smelling of onions and rain.",
        "adjacent": ["market_square"],
    },
}


def town_scene():
    rooms = {}
    for key, spec in ROOMS.items():
        rooms[key] = {
            "name": spec["name"], "size": spec["size"], "desc": spec["desc"],
            "adjacent": [
                {"to": other, "barrier": "open_door"}
                for other in spec["adjacent"]
            ],
        }
    return {
        "location": "Aldermere",
        "time": "late morning",
        "rooms": rooms,
        "positions": {PLAYER: "north_gate"},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _body(name, place, competence, temperament=None, available=True):
    out = {
        "name": name, "place": place, "berth": place,
        "competence": competence, "available": available,
    }
    if temperament:
        out["temperament"] = temperament
    return out


def _claim(body_key, competence, available=True, strength=1.0):
    return {
        "body": body_key, "competence": dict(competence),
        "believed_available": bool(available), "strength": float(strength),
        "as_of_hours": 0.0, "heard_from": None,
    }


def _ready_charter(spec):
    from world.charter import normalize_charter, seed_needs, seed_roster

    state = normalize_charter(spec)
    state["roster"] = seed_roster(state["bodies"])
    state["needs"] = seed_needs(state["bodies"])
    # Authored current assignments and accumulated service make the town feel
    # inhabited on turn one and give promotion a bounded working past.
    state["watch"] = copy.deepcopy(spec.get("watch") or {})
    state["stood"] = copy.deepcopy(spec.get("stood") or {})
    state["minds"] = copy.deepcopy(spec.get("minds") or {})
    state["politics"] = copy.deepcopy(spec.get("politics") or {})
    state["heard_blame"] = copy.deepcopy(spec.get("heard_blame") or {})
    return normalize_charter(state)


def charter_registry():
    commons_bodies = {
        "toma": _body("Toma Reed", "well_house", {"wellkeeping": 2}, {
            "baseline_reactivity": 0.28, "recovery_rate": 0.72}),
        "edrin": _body("Edrin Bale", "mill", {"milling": 2}, {
            "pleasure_sensitivity": 0.66, "overload_threshold": 0.88}),
        "mara": _body("Mara Venn", "bakehouse", {"baking": 2}, {
            "baseline_reactivity": 0.68, "recovery_rate": 0.38}),
        "sable": _body("Sable Hart", "market_square", {"trade": 2}, {
            "baseline_reactivity": 0.44, "overload_threshold": 0.92}),
        "orin": _body("Orin Pike", "market_square", {"carting": 2}, {
            "pleasure_sensitivity": 0.36, "recovery_rate": 0.64}),
        "willa": _body("Willa Crane", "well_house", {"wellkeeping": 1}),
        "rusk": _body("Rusk Marn", "mill", {"milling": 1}),
        "anja": _body("Anja Fen", "bakehouse", {"baking": 1}),
        "dev": _body("Dev Arlo", "market_square", {"trade": 1}),
        "keel": _body("Keel Dorr", "market_square", {"carting": 1}),
    }
    commons = _ready_charter({
        "key": "aldermere_commons",
        "scene": town_scene(),
        "upkeeps": {
            "water_drawn": {"place": "well_house", "level": 0.56,
                             "floor": 0.30, "drift_per_hour": 0.035,
                             "service_per_hour": 0.085,
                             "requires": {"wellkeeping": 1}},
            "grain_milled": {"place": "mill", "level": 0.62,
                              "floor": 0.25, "drift_per_hour": 0.035,
                              "service_per_hour": 0.08,
                              "requires": {"milling": 1}},
            "bread_baked": {"place": "bakehouse", "level": 0.47,
                             "floor": 0.30, "drift_per_hour": 0.05,
                             "service_per_hour": 0.095,
                             "requires": {"baking": 1},
                             "depends_on": ["grain_milled"]},
            "market_stocked": {"place": "market_square", "level": 0.42,
                                "floor": 0.25, "drift_per_hour": 0.04,
                                "service_per_hour": 0.075,
                                "requires": {"trade": 1},
                                "depends_on": ["bread_baked"]},
            "cart_roads": {"place": "market_square", "level": 0.58,
                           "floor": 0.20, "drift_per_hour": 0.018,
                           "service_per_hour": 0.055,
                           "requires": {"carting": 1}},
        },
        "posts": {
            "well_watch": {"place": "well_house", "serves": ["water_drawn"],
                           "requires": {"wellkeeping": 1}},
            "mill_watch": {"place": "mill", "serves": ["grain_milled"],
                           "requires": {"milling": 1}},
            "oven_watch": {"place": "bakehouse", "serves": ["bread_baked"],
                           "requires": {"baking": 1}},
            "market_clerk": {"place": "market_square",
                             "serves": ["market_stocked"],
                             "requires": {"trade": 1}},
            "cart_warden": {"place": "market_square", "serves": ["cart_roads"],
                            "requires": {"carting": 1}},
        },
        "bodies": commons_bodies,
        "priority": ["water_drawn", "grain_milled", "bread_baked",
                     "market_stocked", "cart_roads"],
        "watch": {"well_watch": "toma", "mill_watch": "edrin",
                  "oven_watch": "mara", "market_clerk": "sable",
                  "cart_warden": "orin"},
        "stood": {"toma": {"well_watch": 119},
                  "edrin": {"mill_watch": 83},
                  "mara": {"oven_watch": 211},
                  "sable": {"market_clerk": 57},
                  "orin": {"cart_warden": 34},
                  "willa": {"well_watch": 44},
                  "rusk": {"mill_watch": 31},
                  "anja": {"oven_watch": 68},
                  "dev": {"market_clerk": 19},
                  "keel": {"cart_warden": 27}},
        "minds": {
            "mara": {"edrin": _claim("edrin", {"milling": 2}, strength=.94)},
            "edrin": {"mara": _claim("mara", {"baking": 2}, strength=.82)},
            "sable": {"orin": _claim("orin", {"carting": 2}, strength=.91)},
            "orin": {"sable": _claim("sable", {"trade": 2}, strength=.70)},
        },
        "politics": {"regard": {"mara->edrin": 0.72,
                                  "edrin->mara": 1.25,
                                  "sable->orin": 0.78,
                                  "orin->sable": 1.18},
                     "standing": {"toma": .35, "mara": .25}, "blame": {}},
        "active_places": list(ROOMS),
        "errand_rate": 0.09,
    })

    civic_bodies = {
        "ysra": _body("Captain Ysra Vale", "north_gate", {"command": 2,
                                                            "watch": 2}, {
            "baseline_reactivity": 0.24, "recovery_rate": 0.74,
            "overload_threshold": 0.91}),
        "jory": _body("Jory Flint", "north_gate", {"watch": 2}, {
            "baseline_reactivity": 0.72, "recovery_rate": 0.32}),
        "nella": _body("Nella Quill", "infirmary", {"lampkeeping": 2}, {
            "pain_sensitivity": 0.78, "baseline_reactivity": 0.61}),
        "iven": _body("Sister Iven", "infirmary", {"healing": 2}, {
            "pain_sensitivity": 0.34, "recovery_rate": 0.82}),
        "pell": _body("Pell Arno", "council_hall", {"clerking": 2}, {
            "pleasure_sensitivity": 0.70, "overload_threshold": 0.64}),
        "bram": _body("Bram Cor", "north_gate", {"command": 1, "watch": 1}),
        "mett": _body("Mett Voss", "north_gate", {"command": 1, "watch": 1}),
        "lysa": _body("Lysa Mott", "market_square", {"lampkeeping": 1}),
        "odo": _body("Odo Senn", "infirmary", {"healing": 1}),
        "tavi": _body("Tavi Rook", "council_hall", {"clerking": 1}),
    }
    civic = _ready_charter({
        "key": "aldermere_civic_watch",
        "scene": town_scene(),
        "upkeeps": {
            "gate_watch": {"place": "north_gate", "level": 0.76,
                           "floor": 0.30, "drift_per_hour": 0.035,
                           "service_per_hour": 0.08,
                           "requires": {"watch": 1}},
            # Deliberately fragile: the roster still believes injured Nella is
            # available. The lamps should fail on the first substantial skip.
            "night_lamps": {"place": "market_square", "level": 0.34,
                            "floor": 0.30, "drift_per_hour": 0.055,
                            "service_per_hour": 0.08,
                            "requires": {"lampkeeping": 1}},
            "infirmary_ready": {"place": "infirmary", "level": 0.70,
                                "floor": 0.25, "drift_per_hour": 0.025,
                                "service_per_hour": 0.07,
                                "requires": {"healing": 1}},
            # There is no mason in the roster: this is an honestly unfillable
            # civic obligation, not a scripted story event.
            "bridge_sound": {"place": "riverside", "level": 0.36,
                             "floor": 0.30, "drift_per_hour": 0.035,
                             "service_per_hour": 0.07,
                             "requires": {"masonry": 1}},
            "petitions_sorted": {"place": "council_hall", "level": 0.55,
                                 "floor": 0.20, "drift_per_hour": 0.025,
                                 "service_per_hour": 0.06,
                                 "requires": {"clerking": 1}},
        },
        "posts": {
            "gate_captain": {"place": "north_gate", "serves": ["gate_watch"],
                             "requires": {"command": 1}},
            "gate_guard": {"place": "north_gate", "serves": ["gate_watch"],
                           "requires": {"watch": 1}},
            "lamp_round": {"place": "market_square", "serves": ["night_lamps"],
                           "requires": {"lampkeeping": 1}},
            "healer_watch": {"place": "infirmary",
                             "serves": ["infirmary_ready"],
                             "requires": {"healing": 1}},
            "bridge_warden": {"place": "riverside", "serves": ["bridge_sound"],
                              "requires": {"masonry": 1}},
            "petition_clerk": {"place": "council_hall",
                               "serves": ["petitions_sorted"],
                               "requires": {"clerking": 1}},
        },
        "bodies": civic_bodies,
        "priority": ["gate_watch", "infirmary_ready", "night_lamps",
                     "bridge_sound", "petitions_sorted"],
        "watch": {"gate_captain": "ysra", "gate_guard": "jory",
                  "lamp_round": "nella", "healer_watch": "iven",
                  "petition_clerk": "pell"},
        "stood": {"ysra": {"gate_captain": 306},
                  "jory": {"gate_guard": 48},
                  "nella": {"lamp_round": 96},
                  "iven": {"healer_watch": 174},
                  "pell": {"petition_clerk": 22},
                  "bram": {"gate_captain": 37, "gate_guard": 52},
                  "mett": {"gate_captain": 29, "gate_guard": 46},
                  "lysa": {"lamp_round": 41},
                  "odo": {"healer_watch": 58},
                  "tavi": {"petition_clerk": 33}},
        "minds": {
            "ysra": {"jory": _claim("jory", {"watch": 2}, strength=.88),
                     # Stale firsthand belief: Ysra has not seen Nella injured.
                     "nella": _claim("nella", {"lampkeeping": 2}, True, .73)},
            "jory": {"ysra": _claim("ysra", {"command": 2, "watch": 2},
                                     strength=.92)},
            "iven": {"nella": _claim("nella", {"lampkeeping": 2}, False, .99)},
            "nella": {"iven": _claim("iven", {"healing": 2}, strength=.99)},
        },
        "politics": {"regard": {"ysra->jory": 1.22,
                                  "jory->ysra": 0.66,
                                  "iven->nella": 1.38,
                                  "nella->iven": 1.42},
                     "standing": {"ysra": .9, "iven": .5}, "blame": {}},
        "heard_blame": {"nella": ["ysra"]},
        "active_places": list(ROOMS),
        "errand_rate": 0.07,
    })
    return {"version": 1, "items": {
        "aldermere_commons": {"state": commons, "window_hours": 1.0},
        "aldermere_civic_watch": {"state": civic, "window_hours": 1.0},
    }}


def pre_run_registry(registry):
    """Give the authored population a day of life before the story opens.

    A service count is biography in outline; a simulated day adds the things
    Scene Life can actually pull on: current need/affect, co-presence beliefs,
    hearsay, contested availability, branches, and who personally witnessed
    those branches.  The last two hours introduce one recent disruption after
    the otherwise ordinary day: Nella is laid up and her relief misses the lamp
    round.  The bridge deficiency is not introduced—it emerges because the
    authored registry genuinely has no mason.
    """
    from world.charter import run, summarize

    registry = copy.deepcopy(registry)
    history = {"hours": 26.0, "events": [], "summaries": {}}
    for key, item in registry["items"].items():
        state, events, trace = run(
            item["state"], hours=24.0, window=4.0, seed=17, trace=True)
        if key == "aldermere_civic_watch":
            # A recent event with causal depth, not a prose seed. Nella's
            # injury is authored initial condition; the missed round, dark
            # lamps, institutional blame, witnesses, and news are simulated.
            state["bodies"]["nella"]["available"] = False
            state["bodies"]["nella"]["place"] = "infirmary"
            state["bodies"]["lysa"]["available"] = False
            state["upkeeps"]["night_lamps"]["level"] = 0.34
        state, recent, recent_trace = run(
            state, hours=2.0, window=1.0, seed=99, trace=True)
        events.extend(recent)
        trace.extend(recent_trace)
        if key == "aldermere_civic_watch":
            # Lysa is available to repair the failure after play starts;
            # Nella remains laid up, so the history has a living consequence.
            state["bodies"]["lysa"]["available"] = True
            state["bodies"]["nella"]["available"] = False
            state["bodies"]["nella"]["place"] = "infirmary"
        item["state"] = state
        item["last_elapsed_seconds"] = 26.0 * 3600.0
        item["last_epoch_id"] = "pre-run"
        history["events"].extend({"charter": key, **copy.deepcopy(event)}
                                 for event in events)
        history["summaries"][key] = summarize(state, events, trace)
    return registry, history


def _store_pre_run_events(db, cid, history):
    """Put pre-run branches in the objective ledger, already in the past."""
    from world.mechanics import stable_event_key

    phrases = {
        "upkeep_out_of_band": "{subject} fell below its operating floor",
        "upkeep_restored": "{subject} returned to its operating band",
        "body_unable": "{subject} became unable to continue",
        "body_recovered": "{subject} recovered enough to continue",
        "post_filled_again": "{subject} was staffed again",
        "post_unfilled": "{subject} could not be staffed",
        "post_believed_filled": "{subject} was believed staffed but was not",
    }
    for event in history.get("events") or []:
        charter_key = str(event.get("charter") or "")
        subject = str(event.get("upkeep") or event.get("post")
                      or event.get("body") or "institution")
        kind = str(event.get("kind") or "institution_event")
        what = phrases.get(kind, "{subject} changed state").format(
            subject=subject)
        event_id = stable_event_key(
            "charter-pre-run", cid, charter_key, kind, subject,
            event.get("at_hours"))
        payload = {
            "what": what, "where": str(event.get("place") or ""),
            "where_kind": "room", "witnessed": "",
            "origin": {"charter": charter_key, "epoch_id": "pre-run"},
            "originator": "", "base_turn": -1,
            "disposition": "resolved_fact",
            "charter_event": {key: copy.deepcopy(value)
                              for key, value in event.items()
                              if key != "charter"},
        }
        db.qi(
            "INSERT OR IGNORE INTO world_events"
            "(event_id,chat_id,turn_id,frame_id,occurred_at,duration_seconds,"
            "kind,location_id,payload,seed,committed) "
            "VALUES(?,?,NULL,NULL,?,0,?,?,?,?,?)",
            (event_id, cid, float(event.get("at_hours") or 0.0) * 3600.0,
             "charter_history", str(event.get("place") or ""),
             json.dumps(payload, ensure_ascii=False),
             f"pre-run:{charter_key}", time.time()),
        )


def build_story(db):
    from world.charter_runtime import save_registry

    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps({
            "name": PLAYER,
            "appearance": "A road-worn surveyor carrying a wax tablet and a grey cloak.",
            "senses": "ordinary human senses", "abilities": [],
            "public_history": "A travelling surveyor, new to Aldermere.",
            "private_history": "Rowan has no prior knowledge of Aldermere's disputes.",
        }), "{}"))
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Thirty Turns in Aldermere",
         "A grounded low-fantasy market town whose commons and civic watch "
         "must keep water, bread, trade, lamps, bridge, gate, and infirmary "
         "functioning. Rowan Hale is a newly arrived travelling surveyor.",
         time.time(), persona_id))
    db.wset(cid, "scene", town_scene())
    db.wset(cid, "simulation_clock", {
        "elapsed_seconds": 26.0 * 3600.0, "display": "late morning"})
    db.wset(cid, "dialogue_config", {
        "offscreen_life": "character_agent", "max_offscreen_actors": 2,
        "promote_after_addressed": 3,
    })
    db.wset(cid, "promotion_thresholds", {
        "dialogue": 2, "mention": 4, "auto_dialogue": 3,
    })
    db.wset(cid, "background_config", {
        "scene_life": "full", "max_managed": 6, "max_reactors": 2,
    })
    db.wset(cid, "living_world", {
        "routine_residue": "floor", "scheduled_consequence": "floor",
        "place_obligations": "floor", "antagonist_ladder": "ceiling",
        "rumor_ledger": "floor",
    })
    db.wset(cid, "fiction_model", {
        "genre": {"primary": "grounded low fantasy"},
        "ontology": {"people": "ordinary human"},
        "causal_regimes": ["material and social causality"],
        "scale_rules": {}, "abstraction_rules": {},
    })
    db.wset(cid, "style_guide", {
        "genre": "grounded low fantasy town life",
        "tone": "observant, humane, materially specific, never grandiose",
        "avoid": "generic bustle, omniscient exposition, instant intimacy",
    })
    registry, pre_run = pre_run_registry(charter_registry())
    save_registry(cid, registry)
    _store_pre_run_events(db, cid, pre_run)
    # This is global configuration, but the whole DB is an expendable copy.
    db.set_setting("auto_promote", "1")
    return cid, pre_run


def establish_output():
    from tools.story_drive import _base

    world = town_scene()
    out = _base("director_establish")
    out["location"] = world["location"]
    out["time"] = world["time"]
    out["scene_description"] = (
        "Aldermere at late morning: a working market town under ordinary "
        "strain, entered through its slate-roofed north gate. The duty board "
        "identifies the silver-braided commander speaking quietly beneath it "
        "as Captain Ysra Vale; Jory Flint, the sharp-faced guard beside her, "
        "keeps watching the road while she speaks.")
    out["rooms"] = copy.deepcopy(world["rooms"])
    out["positions"] = copy.deepcopy(world["positions"])
    out["entities"] = {}
    return out


def install_establishment_only():
    """Author the fixture, then leave every played beat to the real models."""
    from llm import llm_quality

    real = llm_quality.complete_validated_json

    def routed(*, role, step_key, system, payload, **kwargs):
        if step_key.split(":", 1)[0] == "director_establish":
            return establish_output()
        return real(role=role, step_key=step_key, system=system,
                    payload=payload, **kwargs)

    llm_quality.complete_validated_json = routed
    for module in list(sys.modules.values()):
        if getattr(module, "complete_validated_json", None) is not None \
                and module is not llm_quality:
            module.complete_validated_json = routed


def _copy_db(source):
    work = tempfile.mkdtemp(prefix="charter-town-")
    target = os.path.join(work, "playtest.db")
    shutil.copy2(source, target)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(source + suffix):
            shutil.copy2(source + suffix, target + suffix)
    return work, target


def _active_content(db, turn_id, key):
    row = db.q(
        "SELECT v.content FROM variants v JOIN steps s ON s.id=v.step_id "
        "WHERE s.turn_id=? AND s.key=? AND v.active=1 ORDER BY v.id DESC LIMIT 1",
        (turn_id, key), one=True)
    if not row:
        return {}
    try:
        value = json.loads(row["content"] or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _warnings(db, turn_id):
    warnings = []
    for row in db.q(
            "SELECT v.content FROM variants v JOIN steps s ON s.id=v.step_id "
            "WHERE s.turn_id=? AND v.active=1", (turn_id,)):
        try:
            content = json.loads(row["content"] or "{}")
        except (TypeError, ValueError):
            continue
        notes = content.get("_engine_notes") if isinstance(content, dict) else None
        warnings.extend(str(item) for item in ((notes or {}).get("warnings") or []))
    return warnings


def _wait_jobs(cid, timeout=90.0):
    from core import jobs

    deadline = time.monotonic() + timeout
    while jobs.active_jobs(cid) and time.monotonic() < deadline:
        time.sleep(0.1)
    return [job.as_dict() for job in jobs.active_jobs(cid)]


def _charter_digest(cid):
    from world.charter_runtime import registry_for

    registry = registry_for(cid)
    out = {}
    for key, item in registry["items"].items():
        state = item["state"]
        out[key] = {
            "clock_hours": round(float(state.get("clock_hours") or 0.0), 3),
            "levels": {name: round(float(value.get("level") or 0.0), 3)
                       for name, value in state["upkeeps"].items()},
            "watch": dict(state.get("watch") or {}),
            "blame": dict((state.get("politics") or {}).get("blame") or {}),
            "bindings": copy.deepcopy(state.get("bindings") or {}),
            "places": {name: value.get("place")
                       for name, value in state["bodies"].items()},
            "available": {name: bool(value.get("available", True))
                          for name, value in state["bodies"].items()},
        }
    return out


def _cast_digest(db, cid):
    rows = db.q(
        "SELECT ch.id,ch.name,cc.status,cc.state FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=? "
        "ORDER BY ch.id", (cid,))
    return [{"id": row["id"], "name": row["name"], "status": row["status"],
             "charter_origin": (json.loads(row["state"] or "{}")
                                .get("charter_origin"))}
            for row in rows]


def _world_event_count(db, cid):
    row = db.q("SELECT COUNT(*) AS n FROM world_events WHERE chat_id=?",
               (cid,), one=True)
    return int(row["n"] if row else 0)


def _write_artifacts(out_dir, rows, initial, final, cid, pre_run=None):
    os.makedirs(out_dir, exist_ok=True)
    transcript = [
        "# Thirty Turns in Aldermere", "",
        "A model-driven playtest through the production Sonder pipeline.",
        "Only the town fixture and opening establishment were authored.",
        "Every player input and narrator output below is exact.", "", "---", "",
    ]
    for row in rows:
        transcript += [f"## Turn {row['turn']}", "", "**Input**", "",
                       row["input"] or "*(silence)*", "", "**Output**", "",
                       row.get("output") or "*(no narrator output)*", ""]
        if row.get("error"):
            transcript += [f"> Pipeline error: `{row['error']}`", ""]
    with open(os.path.join(out_dir, "transcript.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(transcript))
    with open(os.path.join(out_dir, "turns.json"), "w", encoding="utf-8") as handle:
        json.dump({"chat_id_in_disposable_copy": cid,
                   "pre_run": pre_run or {}, "initial": initial,
                   "final": final, "turns": rows}, handle,
                  ensure_ascii=False, indent=2)


def _audit(rows, initial, final, pre_run=None):
    times = [row["seconds"] for row in rows if not row.get("error")]
    calls = [call for row in rows for call in row.get("calls") or []]
    return {
        "turns": len(rows),
        "failed": sum(bool(row.get("error")) for row in rows),
        "median_turn_seconds": statistics.median(times) if times else None,
        "total_turn_seconds": round(sum(times), 3),
        "warnings": sum(len(row.get("warnings") or []) for row in rows),
        "llm_calls": len(calls),
        "llm_seconds": round(sum(float(call.get("sec") or 0.0) for call in calls), 3),
        "background_reactions": sum(
            len((row.get("background") or {}).get("reactions") or []) for row in rows),
        "promoted": [entry for entry in final["cast"]
                     if entry.get("charter_origin")],
        "world_events": final["world_events"],
        "pre_run": pre_run or {},
        "charter_initial": initial["charters"],
        "charter_final": final["charters"],
    }


def play_one(db, cid, turn_number, player_input):
    from agents.runtime import run_pipeline
    from tools.stability_run import Capture

    last = db.q("SELECT MAX(idx) AS idx FROM turns WHERE chat_id=?",
                (cid,), one=True)
    idx = int(last["idx"] + 1) if last and last["idx"] is not None else 0
    tid = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,NULL)", (cid, idx, player_input, time.time()))
    started = time.perf_counter()
    error = ""
    with Capture() as capture:
        try:
            for event in run_pipeline(cid, tid):
                if event.get("type") in ("error", "aborted"):
                    error = str(event)[:300]
        except Exception as exc:  # Report and preserve the partial turn.
            error = f"{type(exc).__name__}: {exc}"[:300]
    pending = _wait_jobs(cid)
    elapsed = time.perf_counter() - started
    narrator = _active_content(db, tid, "narrator")
    background = _active_content(db, tid, "background_react")
    commit = _active_content(db, tid, "commit")
    promotions = (((commit.get("results") or {}).get("promotions") or {})
                  .get("promoted") or [])
    return {
        "turn": turn_number, "turn_id": tid, "input": player_input,
        "output": str(narrator.get("prose") or ""),
        "seconds": round(elapsed, 3), "error": error,
        "warnings": _warnings(db, tid), "calls": capture.calls,
        "background": background, "promotions_this_turn": promotions,
        "charters": _charter_digest(cid), "cast": _cast_digest(db, cid),
        "world_events": _world_event_count(db, cid),
        "pending_jobs": pending,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default="engine.db")
    parser.add_argument("--out", required=True)
    parser.add_argument("--turns", type=int, default=30)
    args = parser.parse_args(argv)

    source = os.path.abspath(args.source)
    out_dir = os.path.abspath(args.out)
    if not os.path.exists(source):
        raise SystemExit(f"source database not found: {source}")
    if os.path.exists(os.path.join(out_dir, "turns.json")):
        raise SystemExit(f"refusing to overwrite completed playtest: {out_dir}")

    work, scratch = _copy_db(source)
    os.environ["ENGINE_DB"] = scratch
    rows = []
    try:
        from core import db
        db.configure(scratch)
        db.init()
        install_establishment_only()
        cid, pre_run = build_story(db)
        initial = {"charters": _charter_digest(cid), "cast": _cast_digest(db, cid),
                   "world_events": _world_event_count(db, cid)}
        print(f"READY chat={cid} disposable_db={scratch}", flush=True)
        print("Type one player declaration per prompt; /finish stops early.", flush=True)
        for number in range(1, max(1, args.turns) + 1):
            try:
                player_input = input(f"INPUT {number}> ")
            except EOFError:
                break
            if player_input.strip().casefold() == "/finish":
                break
            row = play_one(db, cid, number, player_input)
            rows.append(row)
            print(f"\nOUTPUT {number} ({row['seconds']:.1f}s):", flush=True)
            print(row["output"] or "[no narrator output]", flush=True)
            if row["promotions_this_turn"]:
                print("PROMOTION:", json.dumps(row["promotions_this_turn"],
                                                ensure_ascii=False), flush=True)
            if row["error"]:
                print("ERROR:", row["error"], flush=True)
            if row["warnings"]:
                print(f"WARNINGS: {len(row['warnings'])}", flush=True)
            print("", flush=True)
            final = {"charters": row["charters"], "cast": row["cast"],
                     "world_events": row["world_events"]}
            _write_artifacts(out_dir, rows, initial, final, cid, pre_run)
        final = ({"charters": _charter_digest(cid), "cast": _cast_digest(db, cid),
                  "world_events": _world_event_count(db, cid)})
        audit = _audit(rows, initial, final, pre_run)
        _write_artifacts(out_dir, rows, initial, final, cid, pre_run)
        with open(os.path.join(out_dir, "audit.json"), "w", encoding="utf-8") as handle:
            json.dump(audit, handle, ensure_ascii=False, indent=2)
        print("AUDIT:", json.dumps(audit, ensure_ascii=False), flush=True)
        print(f"WROTE {out_dir}", flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
