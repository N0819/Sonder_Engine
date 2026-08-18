import os, sys, time, json
HERE=os.path.dirname(os.path.abspath(__file__))
os.environ["ENGINE_DB"]=os.path.join(HERE,"run.db")
sys.path.insert(0,"/home/nathan/Documents/Fiction-improved/Fiction")
from core import db
from core.db import q, qi, transaction
from persist.checkpoints import ensure_checkpoint
from agents.runtime import run_pipeline
CID=1
pin=sys.argv[1] if len(sys.argv)>1 else ""
with transaction():
    row=q("SELECT MAX(idx) AS m FROM turns WHERE chat_id=?",(CID,),one=True)
    idx=(row["m"]+1) if row and row["m"] is not None else 0
    tid=qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",(CID,idx,pin,time.time(),None))
ensure_checkpoint(CID,idx)
t0=time.time()
for _ in run_pipeline(CID,tid): pass
dur=time.time()-t0
def av(k):
    r=q("SELECT v.content FROM steps s JOIN variants v ON v.step_id=s.id AND v.active=1 WHERE s.turn_id=? AND s.key=?",(tid,k),one=True)
    return json.loads(r["content"]) if r else None
narr=av("narrator") or {}
dr=av("director_resolve") or av("director_establish") or {}
sc=av("outcome_scene") or json.loads(q("SELECT value FROM world WHERE chat_id=1 AND key='scene'",one=True)["value"])
print(f"@@@TURN {idx} ({dur:.0f}s)@@@")
print("INPUT:",pin)
print("PROSE:",narr.get("prose",""))
print("LOCATION:",sc.get("location"))
print("ROOMS:",list((sc.get('rooms') or {}).keys()))
print("POSITIONS:",json.dumps(sc.get("positions")))
with open(os.path.join(HERE,"run_log.jsonl"),"a") as fh:
    fh.write(json.dumps({"idx":idx,"dur":round(dur),"input":pin,"prose":narr.get("prose",""),
                         "location":sc.get("location"),"rooms":list((sc.get('rooms') or {}).keys()),
                         "positions":sc.get("positions")},ensure_ascii=False)+"\n")
