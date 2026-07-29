#!/usr/bin/env python3
"""A ten-turn ordinary-life test story, and the measurements that make it useful.

Deliberately NOT a maze. The maze arms measured navigation and stopped
producing new findings; every defect fixed on 2026-07-29 came out of ordinary
conversation in one room -- repeated dialogue, a contact ledger that never
retired anything, a mind pinned at saturation, and inference memories crushed
to a floor. This runs a small cast through a small, ordinary place and then
measures exactly those things.

Runs against a SCRATCH database. The author's engine.db is opened read-only and
only to carry model/provider configuration, the same way tools/maze_experiment
does it -- a fresh DB has no model for any role and dies on the first call.

  python "play_turn.py" --dry-run          # build the world, no model calls
  python "play_turn.py" --turns 10         # the real thing
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO = os.environ.get("SONDER_REPO", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tools"))


# --- the story ------------------------------------------------------------
#
# One room, two people who already know the player, and nothing dramatic. The
# point is that nothing dramatic happens: that is the condition under which a
# character starts repeating itself, and the condition the maze never tested.

SCENARIO = ("The common room of a small roadside inn, late afternoon. Rain "
            "outside. A fire, a few tables, nobody in a hurry.")

PLAYER_TURNS = [
    'You shake the rain off your coat and drop onto a stool at the bar. "Miserable out there."',
    '"Anything hot? I don\'t much care what."',
    'You warm your hands on the cup. "Quiet today."',
    '"How long have you been running this place?"',
    'You glance at the woman by the fire. "She a regular?"',
    'You carry your cup over to the fire and sit down across from her. "Mind if I join you?"',
    '"I\'m headed east in the morning. Anything I should know about the road?"',
    '"Bandits, or just bad weather?"',
    'You look between the two of them. "You two known each other long?"',
    'You drain the cup and set it down. "I should sleep. Thank you both."',
]


def _sheet(name, pronouns, summary, essence, expression, taboo, values, traits,
           voice_register, intent):
    """A minimally complete character. Every psychology field is filled on
    purpose: CLAUDE.md is explicit that an empty `drive` reads as complete and
    is not, and that the failure shows up fifty beats later looking like a
    model problem."""
    from character_schema import default_character_data
    d = default_character_data()
    d["identity"]["name"] = name
    d["identity"]["pronouns"] = pronouns
    d["embodiment"]["visible"]["summary"] = summary
    d["psychology"]["drive"] = {"essence": essence, "expression": expression,
                                "taboo": taboo}
    d["psychology"]["values"] = values
    d["psychology"]["traits"] = traits
    d["social"]["voice"]["register"] = voice_register
    d["social"]["voice"]["verbosity"] = "natural"
    d["initial_state"]["standing_intentions"] = [
        {"id": "i1", "intent": intent, "priority": 0.7}]
    return d


def cast():
    return [
        _sheet(
            "Marta Quill",
            {"subject": "she", "object": "her", "possessive": "her"},
            "A broad-shouldered woman in her fifties, sleeves pushed up, "
            "flour on one forearm.",
            "keeping a room where people can put their guard down -- it is "
            "never finished, because every night brings strangers who have "
            "not yet done it",
            "she reads a person's shoulders before their face, feeds them "
            "before asking anything, and lets a silence run rather than fill "
            "it",
            "prying. A question asked for her own curiosity rather than the "
            "guest's comfort is the one thing she will not do",
            ["a guest's ease over her own curiosity",
             "honesty over smoothing things over, when the two collide"],
            ["watchful", "dry", "unhurried"],
            "low, unhurried, more comfortable with statements than questions",
            "keep the room easy tonight",
        ),
        _sheet(
            "Ilsabet Vane",
            {"subject": "she", "object": "her", "possessive": "her"},
            "A thin woman with a travelling cloak drying on the chair beside "
            "her, boots still muddy.",
            "getting the measure of a road before she walks it -- there is "
            "always another road, so it cannot be finished",
            "she asks about conditions, prices and people in that order, and "
            "trusts a stranger's account over a posted notice",
            "committing to a route she has not questioned. Repeating a rumour "
            "as though she had confirmed it herself",
            ["a verified detail over a comforting one",
             "speed over comfort, when she must choose"],
            ["direct", "observant", "slow to warm"],
            "clipped, factual, warms only in small increments",
            "learn what the eastern road is actually like",
        ),
    ]


def build(db_path, source_db):
    import db
    db.configure(db_path)
    db.init()

    from maze_experiment import carry_model_config
    n_set, n_prov = carry_model_config(source_db, db_path)
    print(f"  carried {n_set} settings and {n_prov} provider connections")

    from db import qi, wset
    from character_schema import character_name, normalize_persona_data

    persona = normalize_persona_data({
        "name": "Corwin Ash",
        "appearance": "A traveller in a soaked oilskin coat, pack still on.",
        "senses": "ordinary senses",
        "public_history": "A courier between the river towns.",
    })
    pid = qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
             ("Corwin Ash", json.dumps(persona), "{}"))

    chat_id = qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("test-story", pid, SCENARIO, time.time()))

    names = []
    for sheet in cast():
        name = character_name(sheet)
        names.append(name)
        cid = qi("INSERT INTO characters(name,sheet,source,created) "
                 "VALUES(?,?,?,?)",
                 (name, json.dumps(sheet), "{}", time.time()))
        qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
           "VALUES(?,?,'active','{}')", (chat_id, cid))

    # Everyone already knows everyone. Without this the player's own view
    # calls both of them "the unfamiliar person" for the whole story -- the
    # `already_known` seeding in app.py's attach route, done directly.
    known = {}
    roster = names + ["Corwin Ash"]
    for who in roster:
        known[who] = [other for other in roster if other != who]
    wset(chat_id, "known", known)

    wset(chat_id, "scene", {
        "location": "The Drowned Hare",
        "time": "late afternoon",
        "description": SCENARIO,
        "rooms": {
            "common_room": {"name": "Common room",
                            "notes": "Low beams, a fire, six tables, a bar "
                                     "along the north wall.",
                            "adjacent": [{"to": "stairs", "barrier": "open",
                                          "distance": "near"}]},
            "stairs": {"name": "Stairs up", "notes": "Narrow, to the rooms.",
                       "adjacent": [{"to": "common_room", "barrier": "open",
                                     "distance": "near"}]},
        },
        "positions": {"Corwin Ash": "common_room",
                      names[0]: "common_room", names[1]: "common_room"},
        "entities": {}, "attire": {}, "overlays": {},
        "contacts": [], "contained": {}, "scales": {},
    })
    return chat_id, names


def play(chat_id, turns):
    from db import q, qi
    from agents.runtime import run_pipeline

    for i, text in enumerate(PLAYER_TURNS[:turns]):
        last = q("SELECT idx FROM turns WHERE chat_id=? ORDER BY idx DESC "
                 "LIMIT 1", (chat_id,), one=True)
        idx = (last["idx"] + 1) if last else 0
        tid = qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
                 "VALUES(?,?,?,?,?)", (chat_id, idx, text, time.time(), None))
        started = time.time()
        try:
            for _event in run_pipeline(chat_id, tid):
                pass
            print(f"  turn {idx:>2}  ok   {time.time()-started:5.1f}s  {text[:58]}")
        except Exception as exc:
            print(f"  turn {idx:>2}  FAIL {time.time()-started:5.1f}s  "
                  f"{type(exc).__name__}: {str(exc)[:110]}")


def measure(chat_id):
    """The four things today's fixes were about, plus the memory regression."""
    from db import q
    from agents.character import _self_line_refrain, _first_verbatim_repeat

    print("\n" + "=" * 72)

    log = {}
    for row in q("SELECT t.idx AS idx, v.content AS content FROM turns t "
                 "JOIN steps s ON s.turn_id=t.id AND s.key='director_resolve' "
                 "JOIN variants v ON v.step_id=s.id AND v.active=1 "
                 "WHERE t.chat_id=? ORDER BY t.idx", (chat_id,)):
        try:
            entries = json.loads(row["content"]).get("dialogue_log") or []
        except (TypeError, ValueError):
            continue
        for d in entries:
            speaker = str(d.get("speaker") or "")
            quote = str(d.get("exact_quote") or "").strip()
            if speaker and quote:
                log.setdefault(speaker, []).append((row["idx"], quote))

    print("DIALOGUE")
    for speaker, lines in log.items():
        said = [q for _, q in lines]
        repeats = sum(
            1 for i in range(1, len(said))
            if _first_verbatim_repeat([said[i]], said[max(0, i - 6):i]))
        refrain = _self_line_refrain([{"said": s} for s in said[-6:]])
        print(f"  {speaker:16} {len(said):>2} lines  "
              f"verbatim repeats: {repeats}  "
              f"refrain: {refrain or 'none'}")

    print("\nMEMORY  (the regression metric: inference confidence)")
    for row in q("SELECT kind, COUNT(*) n, "
                 "ROUND(AVG(confidence),3) avg_conf, "
                 "SUM(CASE WHEN confidence<=0.09 THEN 1 ELSE 0 END) floored "
                 "FROM memories WHERE chat_id=? GROUP BY kind", (chat_id,)):
        extra = ""
        if row["kind"] == "inference" and row["n"]:
            extra = f"  floored: {row['floored']}/{row['n']}"
            if row["floored"] / row["n"] > 0.3:
                extra += "   <-- REGRESSION STILL PRESENT"
        print(f"  {str(row['kind']):12} n={row['n']:<4} "
              f"avg confidence={row['avg_conf']}{extra}")

    from db import wget
    scene = wget(chat_id, "scene", {}) or {}
    contacts = scene.get("contacts") or []
    print(f"\nCONTACTS  {len(contacts)} standing at end "
          f"(pre-fix behaviour was monotonic growth to the 40 cap)")
    for c in contacts:
        print(f"  {c.get('actor')}/{c.get('actor_part')} -> "
              f"{c.get('target')}/{c.get('target_part')} "
              f"[{c.get('manner')}] unasserted={c.get('unasserted')}")

    warned = q("SELECT COUNT(*) n FROM turns t JOIN steps s ON s.turn_id=t.id "
               "WHERE t.chat_id=? AND s.key='commit'", (chat_id,), one=True)
    print(f"\nTURNS COMMITTED  {warned['n']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=10)
    ap.add_argument("--db", default="/tmp/test-story/story.db")
    ap.add_argument("--source-db", default=os.path.join(REPO, "engine.db"))
    ap.add_argument("--dry-run", action="store_true",
                    help="build the world and stop before any model call")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(args.db + suffix)
        except FileNotFoundError:
            pass

    print(f"scratch db: {args.db}")
    chat_id, names = build(args.db, args.source_db)
    print(f"  chat {chat_id}, cast: {', '.join(names)}")

    if args.dry_run:
        from db import wget
        scene = wget(chat_id, "scene", {})
        print(f"  scene rooms: {list(scene.get('rooms') or {})}")
        print(f"  positions:   {scene.get('positions')}")
        print(f"  known:       {json.dumps(wget(chat_id, 'known', {}))}")
        print("\ndry run: world built, no model calls made.")
        return

    print(f"\nplaying {args.turns} turns:")
    play(chat_id, args.turns)
    measure(chat_id)


if __name__ == "__main__":
    main()
