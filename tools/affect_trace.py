"""What the affect pass read, what Jev answered, what the character was
handed and what it then did -- per character call, to be read as fiction.

The owner, 2026-09-26: "probe what jev answers with vs input and how the
character behaves as a result and ask if it makes sense." Scores against
raters say how often Jev agrees with a reader; a trace says whether a beat
makes sense. `play` runs turns through the real pipeline (the seams
`tools/mood_story_drive.py` drives) with the affect pass recorded, per
character call:

- `before` -- the events, standing concerns and recalled memories this mind
  was asked about; Jev's reading of each (how strongly it stirs and what it
  makes the mind feel, by share; a concern's weight; a memory's strength,
  tone and kinds) and its direct reading of the mood; the emotions the mix
  made of it; the mood carried in and the mood after; the block handed over;
- `reply` -- the block as the payload carried it, and what the character
  said and did;
- `after` -- the character's own acts, Jev's reading of each, the pride,
  shame or frustration they gave and the mood after.

Nothing is changed: each seam is wrapped and called through, and Jev is
deterministic, so a trace is what play did. `show` renders a trace to read.

Usage (ENGINE_DB must name a scratch copy outside the tree):
    python tools/affect_trace.py play --chat 1 --inputs-file chunk.txt --out trace.jsonl [--turns 2]
    python tools/affect_trace.py show --trace trace.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TLS = threading.local()
_LOCK = threading.Lock()
_NOW = {"turn": 0, "input": ""}


def _emit(path, record):
    record = {"turn": _NOW["turn"], **record}
    with _LOCK, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _emotion(e):
    return {"name": e.name, "intensity": e.intensity, "source": e.source, "ref": e.ref, "about": e.about}


def _install(path):
    """Wrap the affect pass's seams and the character call; each wrapper
    calls straight through and records what passed."""
    from agents import character
    from mind import affect_appraisal as appraisal
    from mind import affect_pass as ap

    real_appraise, real_before, real_after = appraisal.appraise, ap.before_call, ap.after_call
    real_agent_json = character._agent_json

    def appraise(state, *args, **kwargs):
        result = real_appraise(state, *args, **kwargs)
        _TLS.appraisal = result
        return result

    def before_call(name, sheet, active, baseline, units, observations=(), memory_context=None,
                    relationships=None, language=None, earlier=None):
        _TLS.appraisal = None
        mood_in = ap.carried(active, baseline, units, earlier)[0]
        felt = real_before(name, sheet, active, baseline, units, observations=observations,
                           memory_context=memory_context, relationships=relationships, language=language,
                           earlier=earlier)
        _TLS.name = name
        _emit(path, {"kind": "before", "name": name, "events": ap.events_from(observations),
                     "concerns": ap.concerns_from(active), "memories": ap.memories_from(memory_context),
                     "appraisal": getattr(_TLS, "appraisal", None),
                     "emotions": [_emotion(e) for e in felt.emotions], "mood_in": mood_in.coords,
                     "mood_out": felt.mood.coords, "block": ap.feelings_block(felt), "asked": felt.asked,
                     "note": felt.note})
        return felt

    def after_call(felt, reply):
        _TLS.appraisal = None
        before, mood_before = len(felt.emotions), dict(felt.mood.coords)
        result = real_after(felt, reply)
        _emit(path, {"kind": "after", "name": getattr(_TLS, "name", ""), "acts": ap.acts_from(reply),
                     "appraisal": getattr(_TLS, "appraisal", None),
                     "emotions": [_emotion(e) for e in result.emotions[before:]], "mood_before": mood_before,
                     "mood_after": result.mood.coords, "stored": ap.given_affect(result)})
        return result

    def agent_json(role, step_key, system, payload, **kwargs):
        out = real_agent_json(role, step_key, system, payload, **kwargs)
        if step_key == "character_kernel":
            self_ = (payload or {}).get("self") or {}
            _emit(path, {"kind": "reply", "name": self_.get("name"), "given": self_.get("feelings"),
                         "sequence": (out or {}).get("sequence")})
        return out

    appraisal.appraise, ap.before_call, ap.after_call = appraise, before_call, after_call
    character._agent_json = agent_json


def play(args):
    import mood_story_drive as drive

    path = Path(args.out)
    _install(path)
    app = drive._app()
    inputs = [c.strip() for c in Path(args.inputs_file).read_text(encoding="utf-8").split("\n---\n") if c.strip()]
    for n, text in enumerate(inputs[: args.turns or None], 1):
        _NOW.update(turn=n, input=text)
        tid, errors = drive.turn(app, args.chat, text)
        _emit(path, {"kind": "turn", "input": text, "turn_id": tid, "narration": drive._narration(tid) if tid else "",
                     "errors": errors})
        if errors:
            raise SystemExit("stopping at the first turn that errored")


# --- reading a trace ----------------------------------------------------------------

def _shares(dist, top=3):
    parts = sorted(((k, v) for k, v in (dist or {}).items() if k != "none" and v >= 0.05), key=lambda kv: -kv[1])
    none = (dist or {}).get("none", 0.0)
    text = ", ".join(f"{k} {v:.2f}" for k, v in parts[:top])
    return text + (f" (nothing much {none:.2f})" if none >= 0.1 else "")


def _profile(coords, top=5):
    from mind import affect_mix as mix

    return ", ".join(f"{n} {v:+.2f}" for n, v in mix.mood_profile(mix.Mood(dict(coords or {})), top=top)) or "(near home)"


def _mood_read(appraisal, top=5):
    spec = sorted((appraisal or {}).get("spectrums", {}).items(), key=lambda kv: -abs(kv[1]))[:top]
    moods = sorted(((k, v) for k, v in ((appraisal or {}).get("moods") or {}).items() if v >= 0.34),
                   key=lambda kv: -kv[1])[:top]
    return (", ".join(f"{k} {v:+.2f}" for k, v in spec) + " | " + ", ".join(f"{k} {v:.2f}" for k, v in moods))


def _conduct(sequence):
    lines = []
    for s in sequence or []:
        if not isinstance(s, dict):
            continue
        if s.get("type") == "speech" and str(s.get("text") or "").strip():
            lines.append(f"Says ({s.get('tone') or '-'}): \"{s['text']}\"")
        elif s.get("type") == "action" and (s.get("attempt") or s.get("observable")):
            lines.append(f"Does: {s.get('attempt') or s.get('observable')}")
    return lines or ["(does nothing)"]


def show(args):
    records = [json.loads(line) for line in Path(args.trace).read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in records:
        if r["kind"] == "turn":
            print(f"\n{'=' * 100}\nTURN {r['turn']} >>> {r['input']}\n--- narration ---\n{(r.get('narration') or '')[:args.narration]}")
        elif r["kind"] == "before":
            a = r.get("appraisal") or {}
            print(f"\n## {r['name']} (turn {r['turn']}) -- BEFORE THE CALL"
                  + ("" if r.get("asked") else f"  [not asked: {r.get('note')}]"))
            print(f"  carried in: {_profile(r.get('mood_in'))}")
            for e in r.get("events") or []:
                x = (a.get("events") or {}).get(e["ref"]) or {}
                print(f"  EVENT {e['ref']}: {e['text'][:170]}\n      -> stirs {x.get('stir', 0):.2f}: {_shares(x.get('stirs'))}")
            for c in r.get("concerns") or []:
                x = (a.get("concerns") or {}).get(c["ref"]) or {}
                print(f"  WORRY {c['ref']}: {c['text'][:150]}\n      -> weighs {x.get('weight', 0):.2f}, "
                      f"stirs {x.get('stir', 0):.2f}: {_shares(x.get('stirs'))}")
            for m in r.get("memories") or []:
                x = (a.get("memories") or {}).get(m["ref"]) or {}
                print(f"  MEMORY: {m['text'][:150]}\n      -> stirs {x.get('strength', 0):.2f}, tone "
                      f"{x.get('tone', 0):+.2f}: {_shares(x.get('kinds'))}")
            print(f"  MOOD READ (spectrums | moods): {_mood_read(a)}")
            print(f"  mood after: {_profile(r.get('mood_out'))}")
            b = r.get("block") or {}
            print(f"  HANDED: now {b.get('now')}\n          beneath {b.get('beneath')}\n          mood {b.get('mood')}")
        elif r["kind"] == "reply":
            print(f"  -- {r['name']} THEN:")
            for line in _conduct(r.get("sequence")):
                print(f"     {line[:260]}")
        elif r["kind"] == "after":
            a = (r.get("appraisal") or {}).get("acts") or {}
            print(f"  -- AFTER, own acts:")
            for act in r.get("acts") or []:
                x = a.get(act["ref"]) or {}
                print(f"     {act['text'][:110]}\n        against {x.get('against_values', 0):.2f}, honours "
                      f"{x.get('honors_values', 0):.2f}, regard {x.get('self_regard', 0):+.2f}, wanted else "
                      f"{x.get('wanted_instead', 0):.2f}, eased/stoked {x.get('eased_or_stoked', 0):+.2f}")
            felt = ", ".join(f"{e['name']} {e['intensity']:.2f}" for e in r.get("emotions") or []) or "nothing"
            stored = (r.get("stored") or {}).get("surface") or {}
            print(f"     felt: {felt}\n     mood after: {_profile(r.get('mood_after'))}  (stored surface: {stored.get('label')})")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("play")
    p.add_argument("--chat", type=int, required=True)
    p.add_argument("--inputs-file", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--turns", type=int, default=0)
    p = sub.add_parser("show")
    p.add_argument("--trace", required=True)
    p.add_argument("--narration", type=int, default=1500)
    args = parser.parse_args()
    if args.mode == "play":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from tools.bubble_drive import _require_scratch

        _require_scratch(os.environ.get("ENGINE_DB", ""))
    {"play": play, "show": show}[args.mode](args)


if __name__ == "__main__":
    main()
