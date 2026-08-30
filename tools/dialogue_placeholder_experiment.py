#!/usr/bin/env python3
"""Why the narrator paraphrases delivered dialogue, and what actually stops it.

Measured against chat 1 turn 3 of the Enterprise-D run, where nine logged lines
from three speakers reached the player's view verbatim and the narrator
returned "gives his approval in that measured, encouraging voice" -- three
times, with correction notes naming the dropped quotes each time.

The prompt is not the variable. `DIALOGUE FIDELITY` is already the strongest
statement in the narrator card ("ABSOLUTE", "NEVER SUMMARISE A SPOKEN LINE")
and names this exact failure ("she tells him plainly"). It failed anyway, and
the retry loop failed twice more. So this measures SHAPES OF THE TASK, not
degrees of insistence.

Arms:
  A baseline    -- the shipped prompt, unchanged. Reproduces the failure.
  B named       -- same, but the view names its speakers instead of labelling
                   them "the spare upright man". Tests whether the descriptor
                   labels are what pushes the model into indirect speech.
  C placeholder -- the model never types a line. It writes prose with {{L1}}
                   ... {{Ln}} where each line belongs, and the engine
                   substitutes the exact text. A line it cannot retype is a
                   line it cannot paraphrase.

Prose is not sacrificed to fidelity: C leaves the model in charge of
placement, attribution, beat order and every sentence around the speech. It
only takes away the retyping.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from language_runtime import raw_card  # noqa: E402
os.environ.setdefault(
    "ENGINE_DB",
    str(ROOT / "demos" / "enterprise-d-artifact" / "enterprise.db"))

from core import db  # noqa: E402

db.configure(os.environ["ENGINE_DB"])

from agents.common import _contains_quote  # noqa: E402
from llm.providers import chat_complete  # noqa: E402

TURN_ID = 4
SAMPLES = int(os.environ.get("SAMPLES", "3"))


def _view_and_quotes():
    row = db.q("SELECT v.content FROM steps s JOIN variants v "
               "ON v.step_id=s.id AND v.active=1 "
               "WHERE s.turn_id=? AND s.key='perception_outcome'",
               (TURN_ID,), one=True)
    view = (json.loads(row["content"])["views"] or {})["player"]
    row = db.q("SELECT v.content FROM steps s JOIN variants v "
               "ON v.step_id=s.id AND v.active=1 "
               "WHERE s.turn_id=? AND s.key='director_resolve'",
               (TURN_ID,), one=True)
    log = json.loads(row["content"]).get("dialogue_log") or []
    player = db.q("SELECT player_input FROM turns WHERE id=?",
                  (TURN_ID,), one=True)["player_input"]
    return view, log, player


def _quote_body(text):
    text = str(text or "").strip()
    m = re.match(r'^[\"“](.*)[\"”]$', text, re.S)
    return (m.group(1) if m else text).strip()


NARRATOR = raw_card("en")["prompts"]["narrator"]

PLACEHOLDER_RULE = """

DIALOGUE PLACEHOLDERS — THIS OVERRIDES DIALOGUE FIDELITY'S INSTRUCTION TO
RETYPE LINES. The delivered lines are listed in `dialogue_lines`, numbered.
Do NOT type any of them. Where a line belongs in your prose, write its token
on its own -- {{L1}}, {{L2}} -- and the engine substitutes the exact words
before the reader sees it.

Everything else is unchanged and still yours: which paragraph a line lands in,
what attribution and action surround it, what order the beats take, and every
sentence that is not a delivered line. Use every token exactly once. Write the
prose as though the real line were already sitting where the token is -- the
attribution and rhythm have to fit the words that will arrive there.
"""


def build_payload(view, log, player, *, named, placeholders):
    lines = [_quote_body(e.get("exact_quote")) for e in log
             if _quote_body(e.get("exact_quote"))]
    speakers = [str(e.get("speaker") or "") for e in log
                if _quote_body(e.get("exact_quote"))]
    if named:
        # The composer labelled unrecognised bodies by appearance. Give the
        # view the names a three-year crewmate would obviously have.
        view = (view.replace("The spare upright man", "Captain Picard")
                    .replace("the spare upright man", "Captain Picard")
                    .replace("The tall", "Commander Riker")
                    .replace("the tall", "Commander Riker")
                    .replace("the seated man", "Captain Picard"))
    payload = {"present_scene": view, "player_declaration": player,
               "paragraph_budget": 4}
    if placeholders:
        payload["dialogue_lines"] = [
            {"token": "{{L%d}}" % (i + 1), "speaker": sp, "line": ln}
            for i, (sp, ln) in enumerate(zip(speakers, lines))]
        # The view still carries the quotes; blanking them would change two
        # variables at once.
    return payload, lines


def substitute(prose, log):
    lines = [_quote_body(e.get("exact_quote")) for e in log
             if _quote_body(e.get("exact_quote"))]
    out = prose
    for i, line in enumerate(lines, 1):
        out = out.replace("{{L%d}}" % i, '"%s"' % line)
    return out


def score(prose, lines):
    normalized = re.sub(r"\s+", " ", prose.casefold())
    kept = sum(1 for q in lines if _contains_quote(normalized, q))
    return kept, len(lines)


def run():
    view, log, player = _view_and_quotes()
    arms = [
        ("A baseline", NARRATOR, dict(named=False, placeholders=False)),
        ("B named", NARRATOR, dict(named=True, placeholders=False)),
        ("C placeholder", NARRATOR + PLACEHOLDER_RULE,
         dict(named=True, placeholders=True)),
    ]
    results = {}
    for label, system, opts in arms:
        payload, lines = build_payload(view, log, player, **opts)
        kept_total = total = 0
        samples = []
        for n in range(SAMPLES):
            started = time.time()
            try:
                raw = chat_complete(
                    "narrator", system,
                    json.dumps(payload, ensure_ascii=False),
                    temperature=0.8, max_tokens=2000, json_mode=True)
                prose = (json.loads(raw) or {}).get("prose") or ""
            except Exception as exc:
                print("   sample %d FAILED: %s" % (n, str(exc)[:120]),
                      flush=True)
                continue
            final = substitute(prose, log) if opts["placeholders"] else prose
            kept, need = score(final, lines)
            kept_total += kept
            total += need
            samples.append({"kept": kept, "of": need,
                            "seconds": round(time.time() - started, 1),
                            "prose": final})
            print("   %s sample %d: %d/%d lines survived (%.0fs)"
                  % (label, n, kept, need, time.time() - started), flush=True)
        results[label] = {"kept": kept_total, "of": total, "samples": samples}
        print("%s TOTAL: %d/%d\n" % (label, kept_total, total), flush=True)

    out = ROOT / "demos" / "enterprise-d-artifact" / "dialogue_experiment.json"
    out.write_text(json.dumps(results, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print("=" * 66)
    for label, data in results.items():
        pct = 100.0 * data["kept"] / max(data["of"], 1)
        print("%-16s %3d/%-3d lines survived  (%.0f%%)"
              % (label, data["kept"], data["of"], pct))
    print("artefact:", out)


if __name__ == "__main__":
    run()
