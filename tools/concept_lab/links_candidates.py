"""How many older memories the link question must quote (LINK_CANDIDATES), measured
on the large lab bank with the engine's own vectors (2026-10-05).

For each labelled (outdated, current) pair of `probes_large.json`, and for each of
the lab's Jev-confirmed links (round C's `links_final.json`), the rank of the older
row among the newer row's older rows by cosine of the stored content vectors. Result:
outdated rows in the top 5 / 10 / 20 for 17 / 22 / 26 of 30 pairs; confirmed links
147 / 179 of 196 in the top 5 / 10 (docs/experiments/SUPERSEDED_LINKS_2026_10_05.md).

Inputs, both made by the lab's own tools into CONCEPT_LAB_DIR:
    .venv/bin/python tools/concept_lab/embed_bank.py load    (the bank, embedded)
    .venv/bin/python tools/concept_lab/round_c.py links      (links_final.json)
then: .venv/bin/python tools/concept_lab/links_candidates.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
os.environ.setdefault("CONCEPT_LAB_BANK", "bank_large.json")
os.environ.setdefault("CONCEPT_LAB_PROBES", "probes_large.json")
sys.path.insert(0, str(HERE))
import lab  # noqa: E402


def main():
    rows = lab._load("bank_rows.json", {}).get("rows") or {}
    if not rows:
        raise SystemExit("run embed_bank.py load first")
    db = sqlite3.connect(f"file:{lab.LAB / 'lab.db'}?mode=ro", uri=True)
    by_id = {i: np.frombuffer(b, dtype=np.float32) for i, b in db.execute("SELECT id, embedding FROM memories")}
    vec = {m: by_id[rid] / (np.linalg.norm(by_id[rid]) or 1.0) for m, rid in rows.items() if rid in by_id}

    def rank(newer, older):
        before = [m for m in lab.ORDER[:lab.ORDER.index(newer)] if m in vec]
        ranked = sorted(before, key=lambda m: -float(vec[newer] @ vec[m]))
        return ranked.index(older) + 1 if older in ranked else None

    pairs = [(t, a) for p in lab.PROBES["recall"] if p["kind"] == "superseded"
             for t in p["targets"] for a in p["antitargets"]
             if lab.MEMS[a]["turn"] < lab.MEMS[t]["turn"]]
    ranks = [rank(t, a) for t, a in sorted(set(pairs))]
    print("labelled pairs", len(ranks), {k: sum(1 for r in ranks if r and r <= k) for k in (5, 10, 20)})
    links = lab._load("links_final.json", {})
    lr = [rank(new, old) for old, news in links.items() for new in news]
    print("lab links", len(lr), {k: sum(1 for r in lr if r and r <= k) for k in (5, 10, 20)})


if __name__ == "__main__":
    main()
