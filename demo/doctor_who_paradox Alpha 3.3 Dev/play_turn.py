"""Headless turn driver for the Doctor Who paradox demo. Writes to run.db beside
this file (durable, never /tmp)."""
import os, sys, time, json
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["ENGINE_DB"] = os.path.join(HERE, "run.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from core import db
from core.db import q, qi, transaction
from persist.checkpoints import ensure_checkpoint
from agents.runtime import run_pipeline

CID = 1
pin = sys.argv[1] if len(sys.argv) > 1 else ""
with transaction():
    row = q("SELECT MAX(idx) AS m FROM turns WHERE chat_id=?", (CID,), one=True)
    idx = (row["m"] + 1) if row and row["m"] is not None else 0
    tid = qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
             (CID, idx, pin, time.time(), None))
ensure_checkpoint(CID, idx)
t0 = time.time()
for _ev in run_pipeline(CID, tid):
    pass
dur = time.time() - t0

def av(k):
    r = q("SELECT v.content FROM steps s JOIN variants v ON v.step_id=s.id AND v.active=1 "
          "WHERE s.turn_id=? AND s.key=?", (tid, k), one=True)
    return json.loads(r["content"]) if r else None

narr = av("narrator") or {}
dr = av("director_resolve") or av("director_establish") or {}
di = av("director_interpret") or {}
print(f"@@@TURN {idx} ({dur:.0f}s)@@@")
print("INPUT:", pin)
print("PROSE:", narr.get("prose", ""))
print("SPOKE:", [d.get("speaker") for d in (dr.get("dialogue_log") or [])])
# Surface world-state signals for the paradox test.
sd = (dr.get("state_diff") or {})
print("LOCATION:", (av("outcome_scene") or {}).get("location") if av("outcome_scene") else "-")
if narr.get("player_act_warnings"): print("PLAYER_ACT_WARN:", narr["player_act_warnings"])
with open(os.path.join(HERE, "run_log.jsonl"), "a") as fh:
    fh.write(json.dumps({"idx": idx, "dur": round(dur), "input": pin,
                         "prose": narr.get("prose", ""),
                         "spoke": [d.get("speaker") for d in (dr.get("dialogue_log") or [])]},
                        ensure_ascii=False) + "\n")
