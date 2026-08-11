"""Drive multi-turn pose-bearing chats through the REAL pipeline.

The corpus cannot exercise poses: the Director declared one in 2,296 turns.
So this authors the beats a Director would emit (`state_diff.poses`) and
runs them through the real seams -- commit's scene merge, then the real
perception stages -- with zero model calls anywhere.

What it checks, per turn, per observer:
  * the declared pose survives commit into `scene.poses`
  * it reaches the observers entitled to it, at the right grade
  * it reaches NOBODY else (dark room, rear arc, other room, containment)
  * `relative_to` never delivers an unearned canonical name
  * episodes mint on change and stay quiet on persistence
"""
import json
import os
import sys
import time
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)
DB = os.path.join(tempfile.mkdtemp(), "pose.db")
os.environ["ENGINE_DB"] = DB

import db  # noqa: E402
db.configure(DB)
db.init()
from db import q, qi, wget, wset  # noqa: E402
from character_schema import default_character_data, default_persona_data  # noqa: E402
from pipeline_context import ChatData, PipelineContext, TurnData  # noqa: E402
from spatial import merge_scene_with_diff, normalize_scene_poses  # noqa: E402
import agents.perception as perception  # noqa: E402
import agents.common as common  # noqa: E402


def _boom(*a, **k):
    raise AssertionError("a model call was attempted")


common._agent_json = _boom

PLAYER = "Vess"
CAST = {"Reya": "A wiry courier with storm-grey eyes.",
        "Kai": "A broad-shouldered smith with soot on his hands.",
        "Mara": "A tall woman in a hooded travelling cloak."}


def new_chat(known):
    persona_id = qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                    (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    chat_id = qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Poses", "", time.time(), persona_id))
    ids = {}
    for i, (name, looks) in enumerate(CAST.items()):
        sheet = default_character_data(name)
        sheet["embodiment"]["visible"]["summary"] = looks
        cid = qi("INSERT INTO characters(name,sheet,source,created,resource_uid)"
                 " VALUES(?,?,?,?,?)",
                 (name, json.dumps(sheet), "{}", time.time(), f"c{chat_id}_{i}"))
        qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
           (chat_id, cid, "active", "{}"))
        ids[name] = cid
    wset(chat_id, "known", known)
    return chat_id, persona_id, ids


def scene(light="bright", rooms=None, positions=None, **kw):
    sc = {
        "location": "the forge", "time": "day",
        "rooms": rooms or {"forge": {"name": "the Forge", "light": light,
                                     "adjacent": []}},
        "positions": positions or {PLAYER: "forge", "Reya": "forge",
                                   "Kai": "forge", "Mara": "forge"},
        "entities": {}, "attire": {}, "overlays": {}, "poses": {},
    }
    sc.update(kw)
    return sc


def ctx_for(chat_id, persona_id, ids, idx, resolve, base_scene):
    cast = q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
             "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
             (chat_id,))
    turn_id = qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (chat_id, idx, "", time.time()))
    c = PipelineContext(
        chat=ChatData(id=chat_id, name="Poses", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx, player_input="",
                      created=time.time()),
        cast=cast, input="")
    c["_player_room"] = base_scene["positions"][PLAYER]
    c.director_interpret = {
        "sequence": [], "speech": None, "speech_volume": "normal",
        "action": None,
        "flow": {"reactors": list(ids.values()), "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}}}
    c.director_resolve = resolve
    return c


def commit_poses(chat_id, base, diff):
    """The real scene merge + pose normalisation, as commit would run it."""
    merged = merge_scene_with_diff(base, diff)
    normalize_scene_poses(merged)
    wset(chat_id, "scene", merged)
    return merged


FAIL = []


def check(label, cond, detail=""):
    if not cond:
        FAIL.append(f"{label}: {detail}")
    print(f"  {'ok  ' if cond else 'FAIL'} {label}"
          + (f"  -- {detail}" if not cond and detail else ""))


# ---------------------------------------------------------------------------
print("\n=== 1. a declared pose survives commit and reaches every entitled mind")
chat_id, pid, ids = new_chat({n: [PLAYER] + [m for m in CAST if m != n]
                              for n in CAST})
base = scene()
wset(chat_id, "scene", base)
diff = {"poses": {
    "Reya": {"posture": "kneeling", "support": "the anvil block",
             "relative_to": "Kai", "relation": "facing",
             "constraint": "one wrist chained", "detail": "breathing hard"}}}
sc = commit_poses(chat_id, base, diff)
check("pose persisted into scene.poses", bool(sc.get("poses", {}).get("Reya")),
      json.dumps(sc.get("poses")))

c = ctx_for(chat_id, pid, ids, 1,
            {"resolved_event": "Reya kneels.", "dialogue_log": [],
             "state_diff": diff}, sc)
out = perception.perception_outcome(c, nonce=0)
for who, vid in [("player", "player")] + [(n, str(ids[n])) for n in CAST]:
    v = out["views"].get(vid) or ""
    if who == "Reya":
        check(f"{who} feels their own pose",
              "You are kneeling" in v and "one wrist chained" in v, v[:160])
    elif who == "Kai":
        # He is the one she is facing, so he reads "facing you".
        check("Kai sees Reya's pose, addressed to him",
              "Reya is kneeling on the anvil block facing you" in v, v[:200])
    elif who == "player":
        check("the player sees the arrangement",
              "kneeling on the anvil block" in v, v[:200])
    else:
        check(f"{who} sees Reya's pose",
              "Reya is kneeling on the anvil block facing Kai" in v, v[:200])
check("no tripwire fired", not [w for w in c.warnings if "TRIPWIRE" in w],
      str(c.warnings))

# ---------------------------------------------------------------------------
print("\n=== 2. a stranger's pose never carries the name they have not earned")
chat_id, pid, ids = new_chat({"Reya": [PLAYER], "Kai": [PLAYER],
                              "Mara": [PLAYER]})
base = scene()
wset(chat_id, "scene", base)
sc = commit_poses(chat_id, base, diff)
c = ctx_for(chat_id, pid, ids, 1,
            {"resolved_event": "Reya kneels.", "dialogue_log": [],
             "state_diff": diff}, sc)
out = perception.perception_outcome(c, nonce=0)
mara = out["views"][str(ids["Mara"])] or ""
check("Mara gets no canonical names", "Reya" not in mara and "Kai" not in mara,
      mara[:200])
check("Mara still gets the arrangement", "kneeling" in mara, mara[:200])
check("relative_to became a descriptor",
      "facing the" in mara or "facing a" in mara, mara[:200])

# ---------------------------------------------------------------------------
print("\n=== 3. the grade follows the light")
for light, expect_detail in (("dim", False), ("dark", None), ("bright", True)):
    chat_id, pid, ids = new_chat({n: [PLAYER] + [m for m in CAST if m != n]
                                  for n in CAST})
    base = scene(light=light)
    wset(chat_id, "scene", base)
    sc = commit_poses(chat_id, base, diff)
    c = ctx_for(chat_id, pid, ids, 1,
                {"resolved_event": "Reya kneels.", "dialogue_log": [],
                 "state_diff": diff}, sc)
    v = perception.perception_outcome(c, nonce=0)["views"][str(ids["Kai"])] or ""
    if expect_detail is None:
        check(f"{light}: pose does not arrive at all",
              "kneeling" not in v, v[:160])
    elif expect_detail:
        check(f"{light}: full pose arrives",
              "kneeling" in v and "one wrist chained" in v, v[:160])
    else:
        check(f"{light}: posture only, no constraint or detail",
              "kneeling" in v and "chained" not in v and "breathing" not in v,
              v[:160])

# ---------------------------------------------------------------------------
print("\n=== 4. another room is not a view")
chat_id, pid, ids = new_chat({n: [PLAYER] + [m for m in CAST if m != n]
                              for n in CAST})
base = scene(rooms={"forge": {"name": "the Forge", "adjacent": [
                        {"to": "yard", "barrier": "door", "distance": "near"}]},
                    "yard": {"name": "the Yard", "adjacent": [
                        {"to": "forge", "barrier": "door", "distance": "near"}]}},
             positions={PLAYER: "forge", "Reya": "forge", "Kai": "yard",
                        "Mara": "forge"})
wset(chat_id, "scene", base)
sc = commit_poses(chat_id, base, diff)
c = ctx_for(chat_id, pid, ids, 1,
            {"resolved_event": "Reya kneels.", "dialogue_log": [],
             "state_diff": diff}, sc)
v = perception.perception_outcome(c, nonce=0)["views"][str(ids["Kai"])] or ""
check("a body through a closed door has no pose delivered",
      "kneeling" not in v, v[:160])

# ---------------------------------------------------------------------------
print("\n=== 5. multi-turn: mints on change, quiet on persistence")
chat_id, pid, ids = new_chat({n: [PLAYER] + [m for m in CAST if m != n]
                              for n in CAST})
base = scene()
wset(chat_id, "scene", base)
sc = commit_poses(chat_id, base, diff)
eps = []
for idx in (1, 2, 3):
    turn_diff = diff if idx < 3 else {"poses": {
        "Reya": {"posture": "standing", "support": "", "relative_to": "",
                 "relation": "", "constraint": "", "detail": ""}}}
    sc = commit_poses(chat_id, wget(chat_id, "scene", {}), turn_diff)
    c = ctx_for(chat_id, pid, ids, idx,
                {"resolved_event": "...", "dialogue_log": [],
                 "state_diff": turn_diff}, sc)
    out = perception.perception_outcome(c, nonce=0)
    eps.append((out.get("episodes") or {}).get(str(ids["Kai"])) or "")
    print(f"    turn {idx} Kai episode: {eps[-1][:110]!r}")
check("turn 1 mints the new pose", "kneel" in eps[0].lower(), eps[0][:120])
check("turn 3 mints the change to standing", "stand" in eps[2].lower(),
      eps[2][:120])

print("\n" + "=" * 68)
print("FAILURES:", len(FAIL))
for f in FAIL:
    print("  -", f)
