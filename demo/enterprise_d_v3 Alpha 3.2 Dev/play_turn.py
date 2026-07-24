"""Headless turn driver for the v3 demo run.

Deliberately writes to run.db beside this file, NOT /tmp: the v3 run before it
was correctly isolated from engine.db but placed in /tmp, and a power cut took
the whole run with it.
"""
import os, sys, time, json
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["ENGINE_DB"] = os.path.join(HERE, "run.db")
sys.path.insert(0, "/home/nathan/Documents/Fiction-improved/Fiction")
import db
from db import q, qi, transaction
from checkpoints import ensure_checkpoint
from agents.runtime import run_pipeline

CID = 28
VORNE = 27
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
print(f"@@@TURN {idx} ({dur:.0f}s)@@@")
print("INPUT:", pin)
print("PROSE:", narr.get("prose", ""))
print("SPOKE:", [d.get("speaker") for d in (dr.get("dialogue_log") or [])])
st = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?", (CID, VORNE), one=True)
if st and st["state"]:
    interior = (json.loads(st["state"]).get("interior") or {})
    print("VORNE strain:", interior.get("drive_strain"),
          "| rupture:", bool(interior.get("drive_rupture")),
          "| former_drives:", len(interior.get("former_drives") or []))
# Append to a durable per-turn log so a crash costs at most the current turn.
with open(os.path.join(HERE, "run_log.jsonl"), "a") as fh:
    fh.write(json.dumps({"idx": idx, "dur": round(dur), "input": pin,
                         "prose": narr.get("prose", ""),
                         "spoke": [d.get("speaker") for d in (dr.get("dialogue_log") or [])]},
                        ensure_ascii=False) + "\n")
