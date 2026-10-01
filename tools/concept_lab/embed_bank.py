"""The large synthetic bank through the engine's REAL recall net (2026-09-30).

The owner: "how badly does reducing the rrf window to 60 and having jev return
on only 24 hurt things for recall?" and "Can we embed our memory bank?"

  load    write the 240 merged memories into a scratch database with the
          production mint path (`prepare_memories_batch` /
          `add_memories_batch`), embedded by the configured embeddings role
          (refuses the crc32 fallback), one chat, one character.
  nets    per recall probe: `memory_jev.memory_net` -- the production
          equal-weight RRF over every lane -- with the scene as the query, the
          goal as an aspect, the 8-turn recent window excluded, over the whole
          visible bank; the fused order is cached.
  score   the delivered set for each net size N and keep K: the net's top N,
          ranked by the whole-bank Jev grades already cached for these probes
          (`recall_1500.json`, MEMORY_CHARS 1500), top K kept. A probe is hit
          when an answer memory is delivered (an answer in the recent window is
          delivered by the recent lane and counted separately).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("CONCEPT_LAB_BANK", "bank_large.json")
os.environ.setdefault("CONCEPT_LAB_PROBES", "probes_large.json")
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

GRADES_DIR = Path(os.environ.get("CONCEPT_LAB_TAGS_DIR", str(lab.LAB)))
RECENT = 8


def load():
    from core import db
    src = sqlite3.connect(f"file:{lab.ROOT / 'engine.db'}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    cols = [r[1] for r in src.execute("pragma table_info(providers)")]
    row = src.execute("select * from providers where id=7").fetchone()
    db.qi(f"INSERT OR REPLACE INTO providers({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
          tuple(row[c] for c in cols))
    models = json.loads(db.get_setting("agent_models") or "{}")
    models["embeddings"] = json.loads(src.execute("select value from settings where key='agent_models'")
                                      .fetchone()[0])["embeddings"]
    db.set_setting("agent_models", json.dumps(models))
    from llm.providers import embed_texts_meta
    probe = embed_texts_meta(["retrieval configuration probe"])
    if probe.fallback:
        raise SystemExit("embeddings fell back to crc32; refusing")
    import time
    now = time.time()
    chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("concept lab large bank", "", now))
    char_id = db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                    (lab.NAME, json.dumps({}), "{}", now))
    from mind.memory_write import add_memories_batch, prepare_memories_batch
    ids = {}
    order = list(lab.ORDER)
    for i in range(0, len(order), 20):
        group = order[i:i + 20]
        prepared = prepare_memories_batch([
            {"chat_id": chat_id, "char_id": char_id, "turn_id": None, "kind": "episodic", "category": "episode",
             "provenance": "witnessed", "salience": 0.6, "content": lab.merged(lab.MEMS[m]),
             "gist": lab.MEMS[m]["experienced"][:240], "turn_idx": lab.MEMS[m]["turn"]} for m in group])
        batch = prepared.get("embedded")
        if batch is not None and getattr(batch, "fallback", False):
            raise SystemExit("embedding fell back mid-bank; refusing")
        for m, rid in zip(group, add_memories_batch(prepared_batch=prepared)):
            ids[m] = rid
        print("written", len(ids), flush=True)
    lab._save("bank_rows.json", {"chat_id": chat_id, "char_id": char_id, "rows": ids,
                                 "model": probe.model_key, "dim": probe.dimensions})


def nets():
    from llm.providers import embed_texts_meta
    from mind import memory_jev
    meta = lab._load("bank_rows.json")
    rows = meta["rows"]
    back = {v: k for k, v in rows.items()}
    recent = lab.ORDER[-RECENT:]
    cache = lab._load("nets.json", {})
    for probe in lab.PROBES["recall"]:
        if probe["id"] in cache:
            continue
        embedded = embed_texts_meta([probe["now"], probe["trying"]])
        _mems, net, lanes, _v = memory_jev.memory_net(
            meta["chat_id"], meta["char_id"], probe["now"], current_turn_idx=len(lab.ORDER) + 1,
            embedded=embedded, aspects=[("goal", probe["trying"])],
            exclude_ids=[rows[m] for m in recent], size=len(lab.ORDER))
        cache[probe["id"]] = {"fused": [back[i] for i in net], "lanes": sorted(lanes)}
        lab._save("nets.json", cache)
    print("nets", len(cache))


def score():
    grades = json.loads((GRADES_DIR / "recall_1500.json").read_text())
    nets_ = lab._load("nets.json")
    recent = set(lab.ORDER[-RECENT:])
    probes = [p for p in lab.PROBES["recall"] if p["id"] in nets_]
    out = {}
    for n in (40, 60, 80, 100, 150, 232):
        for k in (24, 30):
            hit = allhit = inrecent = 0
            by_kind = {}
            for p in probes:
                g = grades[p["id"]]
                net = nets_[p["id"]]["fused"][:n]
                kept = set(sorted(net, key=lambda m: -(g.get(m) or 0))[:k]) | recent
                t = set(p["targets"])
                h = bool(t & kept)
                hit += h
                allhit += t <= kept
                inrecent += bool(t & recent)
                by_kind.setdefault(p["kind"], [0, 0])
                by_kind[p["kind"]][0] += h
                by_kind[p["kind"]][1] += 1
            out[f"net {n} keep {k}"] = {"any_target": hit, "all_targets": allhit, "n": len(probes),
                                        "by_kind": {kk: f"{a}/{b}" for kk, (a, b) in by_kind.items()}}
    # RRF alone, no Jev: first k of the fused order
    for k in (24, 30, 60, 100):
        hit = sum(bool(set(p["targets"]) & (set(nets_[p["id"]]["fused"][:k]) | recent)) for p in probes)
        out[f"rrf only top {k}"] = {"any_target": hit, "n": len(probes)}
    out["answers already in the recent window"] = sum(bool(set(p["targets"]) & recent) for p in probes)
    lab._save("net_score.json", out)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"load": load, "nets": nets, "score": score}[sys.argv[1]]()
