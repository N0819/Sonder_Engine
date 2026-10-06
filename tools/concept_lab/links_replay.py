"""The link question replayed over one character's real bank (2026-10-05).

Every turn memory of the mind (episodic, episode or self), as if newly minted,
against its strictly older rows of the same kinds: the ten most alike by the
stored content vectors, asked of Jev in the lab's state ("YOU ARE <name>.").
engine.db (or CONCEPT_LAB_ENGINE_DB) is opened read-only. Results for chat 64's Doctor and chat 161's Sarah
Moon are in docs/experiments/SUPERSEDED_LINKS_2026_10_05.md.

Usage (after `lab.py setup`, which copies the decision-model provider rows):
    .venv/bin/python tools/concept_lab/links_replay.py <chat_id> <char_id> "<name>"
About ten questions a turn memory; chat 64's 327 rows were 3,258 questions in
20 s, about three cents. Answers cache to CONCEPT_LAB_DIR/links_replay_<chat>_<char>.json.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

QUESTION = ("OLDER MEMORY: {older}\n\nNEWER MEMORY: {newer}\n\nDoes the newer memory change something "
            "the older one states as true -- a figure, a state, where something is, who has it, "
            "whether something still holds?")


def main(chat_id, char_id, name):
    from mind.memory_common import _cos, _vec
    engine = os.environ.get("CONCEPT_LAB_ENGINE_DB") or str(lab.ROOT / "engine.db")
    src = sqlite3.connect(f"file:{engine}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    rows = src.execute(
        "SELECT id, turn_idx, event_key, content, embedding, frame_id FROM memories "
        "WHERE chat_id=? AND char_id=? AND kind='episodic' AND category IN ('episode','self') "
        "AND event_key<>'' AND turn_idx IS NOT NULL ORDER BY turn_idx, id", (chat_id, char_id)).fetchall()
    vecs = {r["id"]: _vec(r["embedding"]) for r in rows}

    def quote(text):
        return " ".join(str(text or "").split())[:1500]

    yn = lab._yesno()
    questions = {}
    for r in rows:
        if r["turn_idx"] < 1:
            continue
        older = [o for o in rows if o["turn_idx"] < r["turn_idx"] and o["frame_id"] == r["frame_id"]]
        for o in sorted(older, key=lambda o: -_cos(vecs[r["id"]], vecs[o["id"]]))[:10]:
            questions[f"{r['id']}|{o['id']}"] = {
                "type": "choice", "criteria": dict(yn),
                "instructions": QUESTION.replace("{older}", quote(o["content"])).replace(
                    "{newer}", quote(r["content"]))}
    answers = lab.ask_jev(f"YOU ARE {name}.", questions,
                          f"links_replay_{chat_id}_{char_id}.json", shard=100)
    linked = [k for k in questions if lab._p_yes(answers.get(k)) >= 0.5]
    newer = {k.split("|")[0] for k in linked}
    print(f"rows {len(rows)} | questions {len(questions)} | yes {len(linked)} "
          f"({len(linked) / max(1, len(questions)):.0%}) | rows with a link {len(newer)}")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
