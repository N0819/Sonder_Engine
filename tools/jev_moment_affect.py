"""Affect lanes for the net: can mood-contrast and mood-match picks be reached?

Measured 2026-09-26 on chat 63 (tools/jev_net_labels.py): every lane the net
had put only 15-16% of Jev's mood_contrast top 10 inside a net of 100. Jev
reads "the moment felt the opposite of how you feel" from what the moment
CONTAINED -- a companion's fear, a tight crawlspace -- while the row's stored
`emotional_context` and `encoding_valence` are the character's OWN feeling at
encoding, which for a steady character barely moves. Two candidate lanes:

- READ TIME, `mood_opposite` / `mood_same`: the affect lexicon's labels of the
  opposite (same) valence sign to the character's surface affect entering
  the beat, embedded as one text and ranked by meaning against every row.
- WRITE TIME, `moment_contrast` / `moment_match`: Jev tags every row ONCE with
  how its moment felt (a five-way choice, the character's own name as the
  state and nothing else), read as a signed valence and arousal; the lanes
  are then arithmetic against the surface affect.

Both are written into each cached beat's `ranks`, so `jev_net_labels.py fit`
can weight them like any other lane.

Usage:
    ENGINE_DB=<a copy> python tools/jev_moment_affect.py --labels labels_63.json \\
        --tags moment_affect_63.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

MOMENT = "How did the moment in this memory feel?"
MOMENT_CHOICES = {
    "tense_unpleasant": ("Tense, frightening or angry: unpleasant and charged.", -1, 1),
    "low_unpleasant": ("Sad, heavy or bleak: unpleasant and subdued.", -1, -1),
    "neutral": ("No particular feeling.", 0, 0),
    "calm_pleasant": ("Calm, warm or content: pleasant and settled.", 1, -1),
    "lively_pleasant": ("Exciting, joyful or fun: pleasant and lively.", 1, 1),
}


def tag_moments(chat_id, char_id, path):
    """Jev's reading of every row's moment, cached: {id: [valence, arousal]}."""
    import jev_memory_probe as probe
    from core.db import q

    out = json.loads(path.read_text()) if path.exists() else {}
    name = q("SELECT name FROM characters WHERE id=?", (char_id,), one=True)["name"]
    rows = [r for r in q("SELECT id, content, gist, turn_idx FROM memories WHERE chat_id=? AND char_id=?",
                         (chat_id, char_id)) if str(r["id"]) not in out]
    if rows:
        questions = {str(r["id"]): {
            "type": "choice",
            "instructions": MOMENT + "\n\n" + probe.memory_text(dict(r), r["turn_idx"] or 0),
            "criteria": {key: label for key, (label, _v, _a) in MOMENT_CHOICES.items()}} for r in rows}
        from llm import decisions
        answers = decisions.decide(f"YOU ARE {name}.", questions)
        for key in questions:
            probs = (answers.get(key) or {}).get("probabilities") or {}
            v = sum(float(probs.get(c) or 0) * cv for c, (_l, cv, _ca) in MOMENT_CHOICES.items())
            a = sum(float(probs.get(c) or 0) * ca for c, (_l, _cv, ca) in MOMENT_CHOICES.items())
            out[key] = [round(v, 4), round(a, 4)]
        path.write_text(json.dumps(out), encoding="utf-8")
    return {int(k): v for k, v in out.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True)
    parser.add_argument("--tags", required=True)
    args = parser.parse_args()

    import jev_net_labels as labels
    from core.db import q
    from llm.providers import embed_texts_meta
    from mind.affect import _ling
    from mind.memory_common import _cos, _vec

    path = Path(args.labels)
    data = json.loads(path.read_text())
    moments = tag_moments(data["chat"], data["char"], Path(args.tags))
    lexicon = _ling("AFFECT_LEXICON")
    rows = {r["id"]: r for r in q("SELECT id, embedding, cue_embedding, embedding_model, embedding_dim "
                                  "FROM memories WHERE chat_id=? AND char_id=?", (data["chat"], data["char"]))}

    def sign(x):
        return (x > 0) - (x < 0)

    for beat in data["beats"]:
        active = labels.state_entering(data["chat"], data["char"], beat["turn_idx"])
        surface = (((active or {}).get("affect") or {}).get("surface") or {})
        v_now, a_now = surface.get("valence"), surface.get("arousal")
        if v_now is None or not sign(float(v_now)):
            continue
        sv, sa = sign(float(v_now)), sign(float(a_now or 0))
        mids = [int(m) for m in beat["judged"]]
        # write time: arithmetic on Jev's tag of each moment
        contrast = sorted((m for m in mids if m in moments), key=lambda m: sv * moments[m][0])
        match = sorted((m for m in mids if m in moments),
                       key=lambda m: -(sv * moments[m][0] + 0.5 * sa * moments[m][1]))
        beat["ranks"]["moment_contrast"] = contrast
        beat["ranks"]["moment_match"] = match
        # read time: the lexicon's opposite / same-valence labels, by meaning
        opposite = [label for label, e in lexicon.items() if e.get("v") == -sv]
        same = [label for label, e in lexicon.items() if e.get("v") == sv and e.get("a") in (sa, 0)]
        embedded = embed_texts_meta(["A moment that felt " + ", ".join(opposite),
                                     "A moment that felt " + ", ".join(same)])
        for lane, vec in (("mood_opposite", embedded.vectors[0]), ("mood_same", embedded.vectors[1])):
            scored = []
            for m in mids:
                r = rows.get(m)
                if not r or r["embedding_model"] != embedded.model_key:
                    continue
                sims = [float(_cos(vec, _vec(b))) for b in (r["embedding"], r["cue_embedding"]) if b]
                if sims:
                    scored.append((max(sims), m))
            beat["ranks"][lane] = [m for _s, m in sorted(scored, reverse=True)]
    path.write_text(json.dumps(data), encoding="utf-8")
    print(f"tagged {len(moments)} moments; affect lanes written for {len(data['beats'])} beats")


if __name__ == "__main__":
    main()
