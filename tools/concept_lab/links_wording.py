"""The superseded-link question's wording, A/B on the large lab bank (2026-10-05).

Five wordings of "does the newer memory change something the older one states
as true?", asked of Jev 1.13 as the lab asked it (state "YOU ARE <name>.", the
two memories merged as the lab merges them) over the 30 labelled
(outdated, current) pairs of `probes_large.json` plus each current row's ten
most alike older rows by TF-IDF. Result (docs/experiments/
SUPERSEDED_LINKS_2026_10_05.md): the lab's own wording linked 25 of 30 pairs.

Usage, from the repo root:
    CONCEPT_LAB_BANK=bank_large.json CONCEPT_LAB_PROBES=probes_large.json \\
        .venv/bin/python tools/concept_lab/lab.py setup
    CONCEPT_LAB_BANK=bank_large.json CONCEPT_LAB_PROBES=probes_large.json \\
        .venv/bin/python tools/concept_lab/links_wording.py
Answers are cached under CONCEPT_LAB_DIR (links_wording.json); a rerun is free.
About 560 Jev questions, under a cent.
"""
from __future__ import annotations

import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("CONCEPT_LAB_BANK", "bank_large.json")
os.environ.setdefault("CONCEPT_LAB_PROBES", "probes_large.json")
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

WORDINGS = {
    "A_lab": ("Does the newer memory change something the older one states as true -- a figure, "
              "a state, where something is, who has it, whether something still holds?"),
    "B_marked": ("Does the newer memory change something the older one states as true -- for "
                 "instance a figure, a state, where something is, who has it, or whether something still holds?"),
    "C_class": "Does the newer memory change something the older one states as true?",
    "D_open": ("Does the newer memory change something the older one states as true -- a figure, "
               "a state, where something is, who has it, whether something still holds, or anything else it states?"),
    "E_whatever": ("Does the newer memory change something the older one states as true? Answer yes "
                   "whatever it changes -- a figure, a state, where something is, who has it, whether something still holds."),
}


def pairs():
    out = set()
    for p in lab.PROBES["recall"]:
        if p["kind"] != "superseded":
            continue
        for a in p["antitargets"]:
            for t in p["targets"]:
                if lab.MEMS[a]["turn"] < lab.MEMS[t]["turn"]:
                    out.add((a, t))
    return sorted(out)


def candidates(labelled):
    docs = {m: re.findall(r"[a-z']+", lab.merged(lab.MEMS[m]).lower()) for m in lab.ORDER}
    df = Counter(w for ws in docs.values() for w in set(ws))
    n = len(docs)

    def vec(ws):
        tf = Counter(ws)
        v = {w: (1 + math.log(c)) * math.log(n / df[w]) for w, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / norm for w, x in v.items()}

    vecs = {m: vec(ws) for m, ws in docs.items()}
    out = set(labelled)
    for t in sorted({t for _a, t in labelled}):
        older = lab.ORDER[:lab.ORDER.index(t)]
        near = sorted(older, key=lambda o: -sum(vecs[t].get(w, 0) * x for w, x in vecs[o].items()))
        out.update((o, t) for o in near[:10])
    return sorted(out)


def main():
    labelled = pairs()
    asked = candidates(labelled)
    yn = lab._yesno()
    questions = {f"{w}|{o}|{t}": {"type": "choice", "criteria": dict(yn), "instructions":
                                  f"OLDER MEMORY: {lab.merged(lab.MEMS[o])}\n\nNEWER MEMORY: "
                                  f"{lab.merged(lab.MEMS[t])}\n\n{text}"}
                 for w, text in WORDINGS.items() for o, t in asked}
    answers = lab.ask_jev(f"YOU ARE {lab.NAME}.", questions, "links_wording.json", shard=100)
    pos = set(labelled)
    for w in WORDINGS:
        def yes(o, t):
            return lab._p_yes(answers.get(f"{w}|{o}|{t}")) >= 0.5
        other = [(o, t) for o, t in asked if (o, t) not in pos]
        print(f"{w:10s} labelled pairs linked {sum(yes(o, t) for o, t in labelled)}/{len(labelled)}"
              f" | other candidates linked {sum(yes(o, t) for o, t in other)}/{len(other)}")


if __name__ == "__main__":
    main()
