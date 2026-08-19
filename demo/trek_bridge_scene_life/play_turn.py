"""Play one turn of the tavern scene-life test and log what the manager did."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["ENGINE_DB"] = os.path.join(HERE, "run.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from core import db
from core.db import q, qi, transaction, wget
from persist.checkpoints import ensure_checkpoint
from agents.runtime import run_pipeline

CID = 1
pin = sys.argv[1] if len(sys.argv) > 1 else ""

with transaction():
    row = q("SELECT MAX(idx) AS m FROM turns WHERE chat_id=?", (CID,), one=True)
    idx = (row["m"] + 1) if row and row["m"] is not None else 0
    tid = qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
             "VALUES(?,?,?,?,?)", (CID, idx, pin, time.time(), None))

ensure_checkpoint(CID, idx)
t0 = time.time()
err = None
try:
    for _ in run_pipeline(CID, tid):
        pass
except Exception as exc:
    err = "%s: %s" % (type(exc).__name__, exc)
dur = time.time() - t0


def av(k):
    r = q("SELECT v.content FROM steps s JOIN variants v "
          "ON v.step_id=s.id AND v.active=1 WHERE s.turn_id=? AND s.key=?",
          (tid, k), one=True)
    return json.loads(r["content"]) if r else None


narr = av("narrator") or {}
br = av("background_react") or {}
presences = wget(CID, "background_presences", {}) or {}

print("@@@ TURN %d (%.0fs)%s @@@" % (idx, dur, " ERROR" if err else ""))
if err:
    print("ERROR:", err)
print("INPUT:", pin)
print("---- PROSE ----")
print(narr.get("prose", ""))
print("---- SCENE MANAGER ----")
print("managed/selected:", br.get("selected"))
for r in (br.get("reactions") or []):
    e = r.get("dialogue_log_entry") or {}
    print("  * %-18s %s%s" % (
        r.get("name"),
        ('"%s"' % e.get("exact_quote")) if e.get("exact_quote") else "(silent)",
        ("  [%s]" % r["action"]) if r.get("action") else ""))
claims = wget(CID, "background_claims", {}) or {}
if claims:
    print("---- CLAIMS ----")
    for rec in claims.values():
        print("  [%s] %s (t%s, credence=%s): %s" % (
            rec.get("status"), rec.get("claimant"), rec.get("turn"),
            rec.get("credence"), rec.get("refs")))
print("---- PRESENCES ----")
for name, rec in presences.items():
    b = rec.get("blurb") or {}
    print("  %-18s blurb=%s" % (name, json.dumps(b, ensure_ascii=False)
                                if b else "-"))
    for t in (rec.get("recent") or []):
        print("      t%s %s" % (t.get("turn"), t.get("text")))

with open(os.path.join(HERE, "run_log.jsonl"), "a") as fh:
    fh.write(json.dumps({
        "idx": idx, "dur": round(dur), "input": pin, "error": err,
        "prose": narr.get("prose", ""),
        "selected": br.get("selected"),
        "reactions": [{"name": r.get("name"),
                       "quote": (r.get("dialogue_log_entry") or {}).get("exact_quote"),
                       "target": (r.get("dialogue_log_entry") or {}).get("intended_target"),
                       "action": r.get("action")}
                      for r in (br.get("reactions") or [])],
        "presences": {n: {"blurb": r.get("blurb"), "recent": r.get("recent")}
                      for n, r in presences.items()},
    }, ensure_ascii=False) + "\n")
