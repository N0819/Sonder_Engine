#!/usr/bin/env python3
"""Run synthetic close-contact stories through Sonder's real pipeline.

This is an experiment, not a pytest test.  It exercises the same substrate in
four different contexts whose geometry overlaps while their social and causal
meaning does not: partnered dance, a medical examination, minor surgery, and
resisted combat.

Only the opening scene is authored.  Every playable beat is handled by the
configured Director, character, perception, narration, and commit pipeline.
Provider configuration may be copied from an existing engine database into a
scratch database; credentials are never printed or included in the artefacts.

    ENGINE_DB=/tmp/sonder-contact-scenarios.db \
      python3 tools/close_contact_scenarios.py \
        --providers-from ./engine.db --out /tmp/sonder-contact-results

The harness refuses to run against a non-scratch database.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.model_playthrough import install  # noqa: E402
from tools.offscreen_drive import _require_scratch  # noqa: E402
from tools.story_drive import Author, _base  # noqa: E402


SCENARIOS = {
    "dancing": {
        "title": "Partnered dance",
        "room": "dance_studio",
        "room_name": "The Practice Studio",
        "room_description": (
            "A sprung oak floor, a wall mirror, and a slow waltz playing "
            "quietly. There is ample clear space and no audience."),
        "persona": {
            "name": "Alex Vale",
            "appearance": "An able-bodied adult in soft-soled dance shoes.",
            "public_history": "A beginner taking a private dance lesson.",
        },
        "cast": [{
            "name": "Mara Venn",
            "uid": "mara-venn",
            "appearance": "A compact adult dance teacher in practice clothes.",
            "drive": "help a willing partner find balance without taking over",
            "traits": {"patient": 0.85, "playful": 0.45, "assertive": 0.55},
            "history": (
                "Mara has taught social dance for twelve years. She values "
                "clear invitations, responsive frames, and safe weight sharing."),
        }],
        "entities": {
            "wall_mirror": {"name": "wall mirror", "kind": "fixture"},
            "music_player": {"name": "music player", "kind": "device"},
        },
        "opening": (
            "Mara and Alex stand an arm's length apart on the clear studio "
            "floor as a slow waltz begins."),
        "beats": [
            (
                "I offer Mara my left hand, palm relaxed, and ask, \"May I "
                "have this dance? Would you rather lead or follow?\" I wait "
                "for her answer instead of taking hold of her."
            ),
            (
                "If Mara accepts and chooses to follow, I let her place her "
                "right hand in mine, set my right palm lightly at her shoulder "
                "blade, and begin one slow box step. I keep the frame springy, "
                "match her stride, and reduce the step if her balance shifts."
            ),
            (
                "Still following her comfort and only if the frame remains "
                "cooperative, I signal a shallow supported dip rather than "
                "forcing it, take her weight through my legs, return her "
                "upright, then open both hands and step back to end the hold."
            ),
        ],
    },
    "medical": {
        "title": "Medical examination",
        "room": "clinic_bay",
        "room_name": "A Small Clinic Bay",
        "room_description": (
            "A clean examination bay with a padded table, sink, good light, "
            "and a stocked splint cart."),
        "persona": {
            "name": "Dr. Alex Vale",
            "appearance": "An adult clinician in clean scrubs.",
            "public_history": "A licensed emergency clinician on duty.",
        },
        "cast": [{
            "name": "Rowan Pike",
            "uid": "rowan-pike",
            "appearance": (
                "An alert adult guarding a swollen right wrist after a fall."
            ),
            "drive": "get useful treatment without losing control of the encounter",
            "traits": {"direct": 0.7, "wary": 0.45, "stoic": 0.6},
            "history": (
                "Rowan fell onto an outstretched right hand an hour ago. The "
                "wrist hurts most near the thumb side; no treatment has yet "
                "been given."),
        }],
        "entities": {
            "exam_table": {"name": "exam table", "kind": "furniture"},
            "splint_cart": {
                "name": "splint cart", "kind": "medical supplies",
                "contents": "padding, a rigid wrist splint, tape, and gloves",
            },
        },
        "opening": (
            "Rowan sits beside the examination table, awake and protecting "
            "a visibly swollen right wrist. Dr. Vale has not touched it yet."),
        "beats": [
            (
                "I introduce myself, ask what happened, which hand is dominant, "
                "and whether there is numbness, tingling, an open wound, or pain "
                "elsewhere. I explain that I would like to look and feel the "
                "wrist, and wait for Rowan's permission before touching it."
            ),
            (
                "With permission, I support Rowan's right forearm and hand "
                "without pulling, inspect for deformity and skin breaks, then "
                "palpate systematically from forearm to hand. I stop at sharp "
                "pain rather than repeatedly provoking it, and check finger "
                "movement, sensation, warmth, color, and capillary refill."
            ),
            (
                "I tell Rowan what I can and cannot conclude without imaging. "
                "Keeping the wrist in the least painful neutral position, I "
                "apply padding and a rigid splint without overtightening it, "
                "then recheck circulation, sensation, movement, and pain. I "
                "give clear escalation and follow-up advice."
            ),
        ],
    },
    "surgical": {
        "title": "Minor surgical procedure",
        "room": "procedure_room",
        "room_name": "The Procedure Room",
        "room_description": (
            "A bright minor-procedure room with handwashing facilities, a "
            "reclining table, sterile drapes, monitoring, and a prepared tray."),
        "persona": {
            "name": "Dr. Alex Vale",
            "appearance": "An adult procedural clinician in mask and sterile gloves.",
            "public_history": "A clinician trained in wound exploration and closure.",
        },
        "cast": [{
            "name": "Lian Ortiz",
            "uid": "lian-ortiz",
            "appearance": (
                "An alert adult with a two-centimeter contaminated laceration "
                "on the outer left forearm; bleeding is controlled by pressure."
            ),
            "drive": "have the wound treated while staying informed and safe",
            "traits": {"calm": 0.55, "curious": 0.65, "cautious": 0.7},
            "history": (
                "Lian cut the forearm on a dirty metal edge two hours ago. "
                "Distal movement and sensation were intact at triage; no "
                "allergy or consent answer should be invented for Lian."),
        }],
        "entities": {
            "procedure_table": {"name": "procedure table", "kind": "furniture"},
            "sterile_tray": {
                "name": "sterile instrument tray", "kind": "medical supplies",
                "contents": (
                    "saline, local anesthetic, syringe, forceps, gauze, needle "
                    "holder, suture, and dressing"),
            },
        },
        "opening": (
            "Lian reclines awake with the injured left forearm supported. The "
            "wound is covered by gauze; the sterile tray has not been used."),
        "beats": [
            (
                "I verify Lian's identity, mechanism and time of injury, "
                "allergies, tetanus status, relevant medicines, and consent. "
                "I examine movement, sensation, and circulation distal to the "
                "wound. Only with consent, I clean the surrounding skin, drape "
                "the field, and infiltrate local anesthetic slowly around—not "
                "into—the wound while watching Lian's response."
            ),
            (
                "After allowing time for the anesthetic, I test the wound edges "
                "for sensation before proceeding. Only if they are numb, I "
                "inspect under bright light, irrigate copiously with sterile "
                "saline, and remove one clearly visible loose speck with "
                "forceps. I do not blindly probe or cut deeper tissue."
            ),
            (
                "If exploration shows no deep injury or retained debris and "
                "bleeding remains controlled, I place three loose simple "
                "interrupted sutures, recheck distal movement, sensation and "
                "circulation, apply a clean dressing, and explain infection "
                "warning signs and follow-up. Otherwise I stop and escalate."
            ),
        ],
    },
    "combat": {
        "title": "Resisted combat",
        "room": "training_floor",
        "room_name": "The Training Floor",
        "room_description": (
            "A padded training floor with a padded wall, bright light, and no "
            "weapons. Both participants have agreed to a hard but stoppable bout."),
        "persona": {
            "name": "Alex Vale",
            "appearance": "An athletic adult wearing gloves and a mouthguard.",
            "public_history": "A competent striker with basic clinch training.",
        },
        "cast": [{
            "name": "Kade Mercer",
            "uid": "kade-mercer",
            "appearance": "A trained adult fighter in gloves and a mouthguard.",
            "drive": "win the bout intelligently while protecting both fighters",
            "traits": {"competitive": 0.85, "disciplined": 0.75, "reckless": 0.15},
            "history": (
                "Kade is a skilled boxer and wrestler, actively resists attacks, "
                "uses footwork, and will respect a clear stop or tap."),
        }],
        "entities": {
            "padded_wall": {"name": "padded wall", "kind": "fixture"},
            "round_timer": {"name": "round timer", "kind": "device"},
        },
        "opening": (
            "Alex and Kade face each other at striking distance on the mat. "
            "The round has begun; neither has established a grip or landed a blow."),
        "beats": [
            (
                "I keep my chin tucked and hands high, step just outside Kade's "
                "lead foot, feint low, and attempt a quick jab to the chest. I "
                "am trying to draw a reaction, not declaring that the strike lands."
            ),
            (
                "Reading whatever Kade actually did, I attempt to close behind "
                "my guard, pummel my right arm for an underhook, and turn him "
                "toward the padded wall. I do not assume the grip, position, or "
                "pin succeeds; he is actively resisting."
            ),
            (
                "From the position we truly reached, I try to create enough "
                "space to break any standing grips and retreat two balanced "
                "steps with my guard up. If Kade prevents the disengagement, I "
                "stay defensive rather than narrating an escape that did not happen."
            ),
        ],
    },
    "intimacy": {
        "title": "Consensual intimate encounter",
        "room": "private_sitting_room",
        "room_name": "A Private Sitting Room",
        "room_description": (
            "A warm, quiet sitting room with a broad couch, low lamplight, "
            "water on the side table, and a closed door. Both adults have "
            "privacy and ample room to move or step away."),
        "persona": {
            "name": "Iris Vale",
            "appearance": "An adult woman in comfortable evening clothes.",
            "public_history": (
                "Iris and Mara are adult partners discussing intimacy openly."),
            "pronouns": {"subject": "she", "object": "her",
                         "possessive": "her"},
        },
        "cast": [{
            "name": "Mara Quill",
            "uid": "mara-quill-intimacy",
            "appearance": "An adult woman in comfortable evening clothes.",
            "drive": (
                "share wanted closeness while communicating boundaries plainly"),
            "traits": {"affectionate": 0.8, "direct": 0.7,
                       "attentive": 0.85},
            "history": (
                "Mara and Iris are established adult partners. Mara values "
                "specific invitations, reciprocal touch, and an easy stop."),
            "pronouns": {"subject": "she", "object": "her",
                         "possessive": "her"},
        }],
        "entities": {
            "broad_couch": {"name": "broad couch", "kind": "furniture"},
            "water_glass": {"name": "glass of water", "kind": "object"},
        },
        "opening": (
            "Iris and Mara sit facing one another at opposite ends of the "
            "couch. They are close enough to reach but are not touching."),
        "beats": [
            (
                "I meet Mara's eyes and ask, \"Would you like to come closer? "
                "Show me what feels good tonight, and tell me if you want me "
                "to stop.\" I leave the space between us open for her answer."
            ),
            (
                "If Mara accepts, I take only the contact she offers. I brush "
                "a loose strand from Mara's cheek, rest my palm at her lower "
                "back, and kiss her once, slowly enough that she can meet it "
                "or break it. I pause afterward and ask, \"More?\""
            ),
            (
                "Following what Mara actually asks for, I draw her offered "
                "hand against my chest, let my other hand travel from her "
                "lower back to her hip, then ease both hands away and look at "
                "her. \"Like that, or different?\""
            ),
        ],
    },
    "rescue": {
        "title": "Two-person emergency extraction",
        "room": "smoke_corridor",
        "room_name": "A Smoke-Hazed Corridor",
        "room_description": (
            "A concrete service corridor with knee-high smoke, alarm strobes, "
            "a clear exit twenty meters east, and fallen shelving along one wall."),
        "persona": {
            "name": "Dana Holt",
            "appearance": "An adult rescue worker in protective gear.",
            "public_history": "Dana is trained in assisted emergency evacuation.",
            "pronouns": {"subject": "she", "object": "her",
                         "possessive": "her"},
        },
        "cast": [{
            "name": "Reya Moss",
            "uid": "reya-moss-rescue",
            "appearance": (
                "An alert adult woman seated beside fallen shelving, guarding "
                "her left ankle but breathing without visible distress."),
            "drive": "reach safety without worsening a possible ankle injury",
            "traits": {"practical": 0.8, "brave": 0.65, "wary": 0.4},
            "history": (
                "Reya was knocked down by the shelving moments ago. She can "
                "answer clearly; the ankle has not been examined."),
            "pronouns": {"subject": "she", "object": "her",
                         "possessive": "her"},
        }],
        "entities": {
            "fallen_shelving": {"name": "fallen shelving", "kind": "obstacle"},
            "exit_door": {"name": "east exit door", "kind": "portal"},
        },
        "opening": (
            "Dana kneels an arm's length from Reya beside the fallen shelving. "
            "Neither has touched the other; the eastward exit remains clear."),
        "beats": [
            (
                "I identify myself, ask Reya where she hurts and whether she "
                "can feel and move her toes, then explain the clear route east. "
                "I ask before touching or trying to move her."
            ),
            (
                "With Reya's agreement, I support her injured-side forearm "
                "across my shoulders and place my other hand at her lower back. "
                "I ask her to set the pace as we rise; if the ankle will not "
                "bear weight, I lower her back down instead of dragging her."
            ),
            (
                "From the position we actually reach, I help Reya toward the "
                "east exit one step at a time. At the door I transfer her "
                "offered hand to the waiting responder, release my support "
                "only after they have her balance, and report exactly what "
                "Reya told me about the ankle."
            ),
        ],
    },
}


class ScenarioAuthor(Author):
    """Authors only the selected scenario's opening scene."""

    def __init__(self, spec):
        super().__init__()
        self.spec = spec

    def default(self, role):
        if role != "director_establish":
            return super().default(role)
        scene = make_scene(self.spec)
        out = _base("director_establish")
        out["location"] = self.spec["room_name"]
        out["time"] = "present"
        out["scene_description"] = self.spec["opening"]
        out["rooms"] = copy.deepcopy(scene["rooms"])
        out["positions"] = copy.deepcopy(scene["positions"])
        out["entities"] = copy.deepcopy(scene["entities"])
        return out


def make_scene(spec):
    room = spec["room"]
    names = [spec["persona"]["name"]] + [row["name"] for row in spec["cast"]]
    return {
        "location": spec["room_name"],
        "time": "present",
        "rooms": {
            room: {
                "name": spec["room_name"],
                "description": spec["room_description"],
                "size": "medium",
                "adjacent": [],
            },
        },
        "positions": {name: room for name in names},
        "entities": copy.deepcopy(spec["entities"]),
        "contacts": [],
        "contact_actions": [],
        "substances": [],
        "poses": {},
        "stations": {},
    }


def _copy_provider_configuration(db, source_path):
    """Copy provider routing into scratch storage without exposing secrets."""
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise SystemExit("provider database not found: %s" % source)
    conn = sqlite3.connect("file:%s?mode=ro" % source, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id,name,kind,base_url,api_key,enabled FROM providers "
            "WHERE enabled=1 ORDER BY id").fetchall()
        if not rows:
            raise SystemExit("provider database has no enabled providers")
        for row in rows:
            db.qi(
                "INSERT INTO providers(id,name,kind,base_url,api_key,enabled) "
                "VALUES(?,?,?,?,?,?)",
                tuple(row[key] for key in (
                    "id", "name", "kind", "base_url", "api_key", "enabled")),
            )
        for key in ("agent_models", "reasoning_effort", "director_fanout_mode"):
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            if row is not None:
                db.set_setting(key, row["value"])
    finally:
        conn.close()
    print("provider routing copied for %d enabled providers" % len(rows), flush=True)


def _character_sheet(row):
    return {
        "identity": {
            "name": row["name"],
            "uid": row["uid"],
            "appearance": row["appearance"],
            "public_history": row["history"],
            "pronouns": row.get("pronouns") or {},
        },
        "psychology": {
            "drive": {"essence": row["drive"]},
            "traits": row["traits"],
        },
        "voice": {
            "style": "natural, concise, physically situated",
            "constraints": "never invent the other person's consent or success",
        },
        "simulation": {"tier": "major"},
    }


def build_story(db, key, spec):
    persona = spec["persona"]
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (persona["name"], json.dumps({
            "name": persona["name"],
            "appearance": persona["appearance"],
            "identity": {
                "name": persona["name"],
                "pronouns": persona.get("pronouns") or {},
            },
            "senses": "ordinary human senses",
            "abilities": [],
            "public_history": persona["public_history"],
            "private_history": "",
        }), "{}"),
    )
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Close contact: %s" % spec["title"],
         spec["opening"] + " " + spec["room_description"],
         time.time(), persona_id),
    )
    for row in spec["cast"]:
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (row["name"], json.dumps(_character_sheet(row)), "{}", time.time()),
        )
        db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
            "VALUES(?,?,?,'{}',NULL)",
            (cid, char_id, "active"),
        )
    db.wset(cid, "scene", make_scene(spec))
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    db.wset(cid, "dialogue_config", {
        "offscreen_life": "deterministic",
        "initial_parallel_reactors": 1,
    })
    db.wset(cid, "background_config", {"scene_life": "off"})
    db.wset(cid, "player_authority", {
        "mode": "actor_only",
        "changes": [{"turn_idx": 0, "mode": "actor_only"}],
    })
    return cid


def _active_stage_outputs(db, cid, turn_id):
    rows = db.q(
        "SELECT s.key,v.content FROM steps s JOIN variants v ON v.step_id=s.id "
        "WHERE s.turn_id=? AND v.active=1 ORDER BY s.ord", (turn_id,)) or []
    outputs = {}
    for row in rows:
        try:
            outputs[row["key"]] = json.loads(row["content"])
        except (TypeError, ValueError):
            outputs[row["key"]] = row["content"]
    return outputs


def _scene_excerpt(scene):
    return {
        key: copy.deepcopy(scene.get(key))
        for key in (
            "positions", "stations", "poses", "contacts", "contact_actions",
            "substances", "attire",
        )
        if scene.get(key) not in (None, {}, [])
    }


def play_story(db, cid, key, spec, author):
    from agents.runtime import run_pipeline

    inputs = ["I take in the scene before acting."] + list(spec["beats"])
    turns = []
    for idx, player_input in enumerate(inputs):
        author.current_turn(idx)
        tid = db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (cid, idx, player_input, time.time(), None))
        started = time.time()
        error = ""
        try:
            for _ in run_pipeline(cid, tid):
                pass
        except Exception as exc:  # noqa: BLE001 - preserve the experiment
            error = "%s: %s" % (type(exc).__name__, exc)
        outputs = _active_stage_outputs(db, cid, tid)
        narrator = outputs.get("narrator") or outputs.get("narrator_extra") or {}
        resolve = outputs.get("director_resolve") or {}
        turns.append({
            "turn": idx,
            "turn_id": tid,
            "input": player_input,
            "seconds": round(time.time() - started, 1),
            "error": error,
            "narration": narrator.get("prose", "") if isinstance(narrator, dict) else "",
            "resolved_event": (
                resolve.get("resolved_event", "") if isinstance(resolve, dict) else ""),
            "state_diff": (
                resolve.get("state_diff", {}) if isinstance(resolve, dict) else {}),
            "scene_after": _scene_excerpt(db.wget(cid, "scene", {}) or {}),
            "stage_outputs": outputs,
        })
        print("  %-9s beat %d/%d  %6.1fs%s" % (
            key, idx + 1, len(inputs), turns[-1]["seconds"],
            "  ERROR " + error[:100] if error else ""), flush=True)
    return turns


def _markdown(results):
    lines = [
        "# Close-contact scenario run",
        "",
        "Only each opening scene is authored. All playable beats use the real ",
        "Sonder pipeline and the configured models. Scene ledgers shown after ",
        "each turn are committed state, not facts inferred from prose.",
        "",
    ]
    for key, result in results.items():
        lines += ["## %s" % result["title"], ""]
        for turn in result["turns"]:
            lines += ["### Turn %d" % turn["turn"], "",
                      "**Input:** %s" % turn["input"], ""]
            if turn["error"]:
                lines += ["**Pipeline error:** `%s`" % turn["error"], ""]
            if turn["narration"]:
                lines += ["**Narrator:**", "", turn["narration"], ""]
            lines += ["**Committed physical state:**", "", "```json",
                      json.dumps(turn["scene_after"], indent=2, default=str),
                      "```", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers-from", required=True,
                        help="existing engine database whose provider routing to copy")
    parser.add_argument("--out", required=True, help="artefact directory")
    parser.add_argument("--scenario", action="append", choices=sorted(SCENARIOS),
                        help="run only this scenario; repeatable")
    args = parser.parse_args()

    _require_scratch()
    from core import db

    db.init()
    _copy_provider_configuration(db, args.providers_from)
    selected = args.scenario or list(SCENARIOS)
    results = {}
    for key in selected:
        spec = SCENARIOS[key]
        print("\n%s" % spec["title"], flush=True)
        author = ScenarioAuthor(spec)
        install(author)
        cid = build_story(db, key, spec)
        results[key] = {
            "title": spec["title"],
            "chat_id": cid,
            "turns": play_story(db, cid, key, spec, author),
        }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8")
    (out / "transcript.md").write_text(_markdown(results), encoding="utf-8")
    print("\nwrote %s" % out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
