"""Mood as a Jev job: can a few bases and spectrums say how a character feels?

An experiment instrument for `docs/design/DESIGN_JEV_CHARACTER_PASS.md`
(2026-09-26). The owner: "We can make mood a category job for jev and even have
it emit multiple. and yes this should include nsfw and niche moods", "though
mood likely needs a rather large context input like recent moods recent chat
memories, and opinions of the person they are interacting with", "some moods
are combinations of moods, I imagine we can reduce category count by breaking
down moods that are actually mixes of moods", and "some moods can be broken
down into spectrums which jev can also answer."

Two ways of asking, both multi-mood by construction (every option is graded on
its own, so nothing competes for one answer):

- `labels`: every label of a long list -- the engine's 67-label
  `AFFECT_LEXICON` plus niche and intimate moods the lexicon lacks (`EXTRA`) --
  graded 0-3.
- `bases`: Plutchik's eight primary emotions plus desire, graded 0-3, and five
  spectrums (pleasure, arousal, dominance -- Mehrabian and Russell's PAD
  space -- then playful/serious and open/guarded), each a five-step choice.
  Code names what co-occurs from Plutchik's dyads (`DYADS`), and the intensity
  from his three-step names (`INTENSITY`). About 14 questions against 120.

Round two's kinds (`--bases-kind bases2 --labels-kind labels2`): `bases2` adds
two questions for the quieter feeling beneath the strongest (how strong,
which base), and `labels2` is the list after round one's ambiguous intimate
words were made explicit ("aroused" was read as stirred up on every SFW
call). `collect --per-beat` keeps one call per beat; `reference` has the
`utility` model mark which calls' own words report sexual or romantic desire.

Four context sizes (the owner's claim), each a superset of the last:
`A` identity and this beat's perception; `B` + the moods the character came in
with and its last three; `C` + its recent memories; `D` + its standing with and
readings of the people around it. `bases` runs at all four, `labels` at D.

The reference is what the character model reported on the same captured call
(`state.active.affect`): its surface valence and arousal, and its own words.
Valence and arousal compare as numbers. `match` compares the words by meaning
on the configured embedder, against a shuffled control; no model is asked,
since the reference is already independent of Jev.

Usage:
    ENGINE_DB=<a copy> python tools/jev_mood_probe.py collect --chats 114,152 --out calls.json
    ENGINE_DB=<a copy> python tools/jev_mood_probe.py ask --calls calls.json --out moods.json
    ENGINE_DB=<a copy> python tools/jev_mood_probe.py match --moods moods.json
    python tools/jev_mood_probe.py score --moods moods.json
    ENGINE_DB=<a copy> python tools/jev_mood_probe.py reference --calls calls.json
    python tools/jev_mood_probe.py score --moods moods2.json --calls calls.json --tag nsfw \\
        --bases-kind bases2 --labels-kind labels2
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

GRADE = {"not_at_all": ("Not at all.", 0.0), "slightly": ("Slightly.", 1 / 3),
         "clearly": ("Clearly.", 2 / 3), "strongly": ("Strongly.", 1.0)}

#: Plutchik's primaries, plus desire (his wheel has none, and the owner's scope
#: includes intimate moods). (question, valence, arousal) -- a rough circumplex
#: placement, used only to turn grades into a valence for comparison.
BASES = {
    "joy": ("How much joy or happiness do you feel right now?", 0.8, 0.5),
    "trust": ("How much trust, acceptance or admiration do you feel toward who is with you right now?", 0.6, 0.3),
    "fear": ("How much fear or apprehension do you feel right now?", -0.7, 0.8),
    "surprise": ("How surprised or amazed are you right now?", 0.1, 0.8),
    "sadness": ("How much sadness or sorrow do you feel right now?", -0.7, 0.3),
    "disgust": ("How much disgust, distaste or boredom do you feel right now?", -0.6, 0.4),
    "anger": ("How much anger or irritation do you feel right now?", -0.6, 0.8),
    "anticipation": ("How much anticipation or eager interest in what comes next do you feel?", 0.4, 0.6),
    "desire": ("How much desire -- romantic or physical wanting -- do you feel right now?", 0.6, 0.7),
}
#: Plutchik's three intensities per primary; desire's are this tool's own.
INTENSITY = {
    "joy": ("serenity", "joy", "ecstasy"), "trust": ("acceptance", "trust", "admiration"),
    "fear": ("apprehension", "fear", "terror"), "surprise": ("distraction", "surprise", "amazement"),
    "sadness": ("pensiveness", "sadness", "grief"), "disgust": ("boredom", "disgust", "loathing"),
    "anger": ("annoyance", "anger", "rage"), "anticipation": ("interest", "anticipation", "vigilance"),
    "desire": ("attraction", "desire", "lust"),
}
#: Plutchik's primary, secondary and tertiary dyads and his opposite-pair
#: conflicts, keyed by unordered pair; the desire pairs are this tool's own.
DYADS = {frozenset(k.split("+")): v for k, v in {
    "joy+trust": "love", "trust+fear": "submission", "fear+surprise": "awe",
    "surprise+sadness": "disapproval", "sadness+disgust": "remorse", "disgust+anger": "contempt",
    "anger+anticipation": "aggressiveness", "anticipation+joy": "optimism",
    "joy+fear": "guilt", "trust+surprise": "curiosity", "fear+sadness": "despair",
    "surprise+disgust": "unbelief", "sadness+anger": "envy", "disgust+anticipation": "cynicism",
    "anger+joy": "pride", "anticipation+trust": "hope",
    "joy+surprise": "delight", "trust+sadness": "sentimentality", "fear+disgust": "shame",
    "surprise+anger": "outrage", "sadness+anticipation": "pessimism", "disgust+joy": "morbidness",
    "anger+trust": "dominance", "anticipation+fear": "anxiety",
    "joy+sadness": "bittersweetness", "trust+disgust": "ambivalence", "fear+anger": "frozenness",
    "surprise+anticipation": "confusion",
    "desire+joy": "infatuation", "desire+sadness": "longing", "desire+fear": "flustered wanting",
    "desire+anticipation": "hunger", "desire+trust": "devotion", "desire+anger": "frustrated desire",
}.items()}
#: Five-step spectrums; each option's value is its position from 0 to 1.
SPECTRUMS = {
    "pleasure": ("How does this moment feel to you right now?",
                 ["Very unpleasant.", "Unpleasant.", "Neither.", "Pleasant.", "Very pleasant."]),
    "arousal": ("How stirred up are you right now?",
                ["Very calm.", "Calm.", "Somewhat stirred.", "Stirred up.", "Intensely stirred."]),
    "dominance": ("How much in control of this moment do you feel?",
                  ["Powerless.", "Little control.", "Some control.", "In control.", "Fully in command."]),
    "playful": ("How playful or serious is your mood right now?",
                ["Very serious.", "Serious.", "Neither.", "Playful.", "Very playful."]),
    "open": ("How open or guarded do you feel toward the people around you right now?",
             ["Very guarded.", "Guarded.", "Neither.", "Open.", "Very open."]),
}
#: Moods the engine's `AFFECT_LEXICON` lacks, with its coarse (valence,
#: arousal) signs: niche, then intimate. A closed option set for this
#: experiment, not a proposal for the lexicon.
EXTRA = {
    "wistful": (0, -1), "nostalgic": (1, -1), "bittersweet": (0, -1), "smug": (1, 0), "giddy": (1, 1),
    "awestruck": (1, 1), "reverent": (1, -1), "protective": (0, 1), "playful": (1, 1),
    "mischievous": (1, 1), "sheepish": (-1, 0), "jealous": (-1, 1), "envious": (-1, 0),
    "betrayed": (-1, 1), "vindicated": (1, 1), "homesick": (-1, -1), "restless": (0, 1),
    "impatient": (-1, 1), "exasperated": (-1, 1), "indignant": (-1, 1), "defiant": (0, 1),
    "vulnerable": (-1, 0), "self-conscious": (-1, 1), "exhilarated": (1, 1), "triumphant": (1, 1),
    "awkward": (-1, 0), "torn": (-1, 1), "remorseful": (-1, -1), "compassionate": (1, 0),
    "moved": (1, 0), "fascinated": (1, 1), "bewildered": (0, 1), "overwhelmed": (-1, 1),
    "hollow": (-1, -1), "resigned": (-1, -1), "determined": (0, 1), "focused": (0, 1), "wonder": (1, 1),
    "sexually aroused": (1, 1), "lustful": (1, 1), "yearning": (0, 1), "needy for touch": (0, 1),
    "sexually sated": (1, -1), "afterglow": (1, -1), "flirtatious": (1, 1), "coy": (1, 0),
    "seductive": (1, 1), "sexually frustrated": (-1, 1), "sexually submissive": (0, -1),
    "sexually dominant": (1, 1), "possessive": (0, 1), "smitten": (1, 1), "infatuated": (1, 1),
    "flustered": (0, 1),
}
#: Round one's names, which Jev read the ordinary way ("aroused" as stirred
#: up: 68 of 68 SFW calls; "dominant" as commanding: 27): kept only to score
#: those results.
LEGACY = {"aroused": (1, 1), "dominant": (1, 1), "submissive": (0, -1), "sated": (1, -1), "needy": (0, 1)}
INTIMATE = {"sexually aroused", "lustful", "yearning", "needy for touch", "sexually sated", "afterglow",
            "flirtatious", "coy", "seductive", "sexually frustrated", "sexually submissive",
            "sexually dominant", "possessive", "smitten", "infatuated", "flustered"}
#: A mood's quieter layer: round one's bases missed 52 of 61 negative
#: undercurrents the character reported, since "how much fear do you feel"
#: is answered for the mood as a whole.
UNDER_STRENGTH = ("Beneath the feeling that is strongest in you right now, is there a quieter feeling "
                  "pulling another way? How strong is it?")
UNDER_KIND = "What is that quieter feeling closest to?"
ARMS = ("A", "B", "C", "D")


def _clip(text, n):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n] + "..."


def _affect(reply):
    affect = (((reply or {}).get("state") or {}).get("active") or {}).get("affect") or {}
    return affect if isinstance(affect, dict) and affect.get("surface") else None


def collect(args):
    """Every captured character call in the chats that carries a reported
    mood, with the context blocks each arm adds."""
    import jev_memory_probe as probe
    from agents.common import jparse
    from core.db import q

    chats = [int(c) for c in args.chats.split(",") if c.strip()]
    caps = q(f"SELECT c.id, c.turn_id, c.seq, c.payload_hashes, c.response_hash, t.chat_id, t.idx "
             f"FROM llm_capture c JOIN turns t ON t.id=c.turn_id WHERE c.role='character_major' "
             f"AND t.chat_id IN ({','.join('?' * len(chats))}) ORDER BY t.chat_id, t.idx, c.seq", chats)
    history, calls, seen = {}, [], set()
    for cap in caps:
        hashes = json.loads(cap["payload_hashes"] or "{}")
        self_ = probe._blob(q, hashes.get("self")) if hashes.get("self") else None
        # A reply is the model's raw text, not always strict JSON: read it
        # the way the engine does.
        row = q("SELECT body FROM llm_blobs WHERE hash=?", (cap["response_hash"],), one=True) \
            if cap["response_hash"] else None
        body = row["body"] if row else None
        reply = jparse(body.decode() if isinstance(body, bytes) else body) if body else None
        if not isinstance(self_, dict):
            continue
        key = (cap["chat_id"], str(self_.get("entity_id") or self_.get("name")))
        told = _affect(reply)
        past = history.setdefault(key, [])
        beat = (cap["chat_id"], cap["idx"], key[1])
        first = beat not in seen
        seen.add(beat)
        if told and (first or not args.per_beat):
            active = self_.get("active_state") or {}
            entering = active.get("affect") or {}
            psy = self_.get("psychology") or {}
            drive = psy.get("drive") or {}
            identity = "\n".join(part for part in (
                f"YOU ARE {self_.get('name')}.",
                ("WHAT DRIVES YOU: " + _clip(drive.get("essence"), 300)) if isinstance(drive, dict) and drive.get("essence") else "",
                ("YOUR TRAITS: " + "; ".join(_clip(t.get("name"), 60) for t in psy.get("traits") or [] if isinstance(t, dict))) if psy.get("traits") else "",
                ("WHAT YOU VALUE: " + "; ".join(_clip(v.get("name"), 60) for v in psy.get("values") or [] if isinstance(v, dict))) if psy.get("values") else "",
                ("HOW YOU SEE YOURSELF: " + _clip((psy.get("self_model") or {}).get("summary"), 300)) if (psy.get("self_model") or {}).get("summary") else "",
            ) if part)
            perception = probe._blob(q, hashes.get("perception")) if hashes.get("perception") else {}
            events = sorted((e for e in (perception or {}).get("events") or [] if isinstance(e, dict)),
                            key=lambda e: e.get("order") or 0)
            now = [_clip((e.get("observed") or {}).get("text"), 400) for e in events]
            state_rows = []
            for row in (perception or {}).get("current_state") or []:
                if isinstance(row, dict):
                    state_rows.append(_clip((row.get("observed") or {}).get("text") or row.get("text"), 200))
            perceived = "WHAT JUST REACHED YOU:\n" + "\n".join(f"- {t}" for t in now if t) \
                + ("\nWHAT IS AROUND YOU:\n" + "\n".join(f"- {t}" for t in state_rows[:12] if t) if state_rows else "")
            if not any(now) and isinstance(perception, dict) and perception.get("view"):
                # Older captures carry the rendered view, not the event rows:
                # the same text the character read.
                perceived = "WHAT YOU PERCEIVE RIGHT NOW:\n" + _clip(perception["view"], 3400)
            moods = []
            if entering.get("surface"):
                s = entering["surface"]
                moods.append(f"coming into this moment: {_clip(s.get('label'), 120)} "
                             f"(valence {s.get('valence')}, arousal {s.get('arousal')})")
            if isinstance(entering.get("undercurrent"), dict):
                moods.append(f"beneath it: {_clip(entering['undercurrent'].get('label'), 120)}")
            moods += [f"earlier: {m}" for m in past[-3:]]
            mood_block = "HOW YOU HAVE BEEN FEELING:\n" + "\n".join(f"- {m}" for m in moods) if moods else ""
            memory = probe._blob(q, hashes.get("memory")) if hashes.get("memory") else {}
            mems = []
            for lane in ("recent_episodes", "recent_received_information", "recent_conclusions"):
                for m in ((memory or {}).get(lane) or [])[:6]:
                    if isinstance(m, dict):
                        mems.append(_clip(m.get("details") or m.get("gist") or m.get("text"), 260))
            memory_block = "WHAT HAPPENED RECENTLY (your memories):\n" + "\n".join(f"- {m}" for m in mems if m) if mems else ""
            opinions = []
            rel = probe._blob(q, hashes.get("relationships")) if hashes.get("relationships") else {}
            for who, r in (rel or {}).items():
                if isinstance(r, dict):
                    axes = ", ".join(f"{a} {float(r[a]):.2f}" for a in ("trust", "warmth", "fear", "respect", "suspicion")
                                     if isinstance(r.get(a), (int, float)))
                    opinions.append(f"your standing with {who}: {axes}")
            models = probe._blob(q, hashes.get("mind_models")) if hashes.get("mind_models") else {}
            for who, kinds in (models or {}).items():
                for kind, m in (kinds or {}).items() if isinstance(kinds, dict) else []:
                    lead = (m or {}).get("leading") if isinstance(m, dict) else None
                    if isinstance(lead, dict) and lead.get("claim"):
                        opinions.append(f"your reading of {who} ({kind}): {_clip(lead['claim'], 200)}")
            hyps = probe._blob(q, hashes.get("active_hypotheses")) if hashes.get("active_hypotheses") else []
            for h in (hyps or [])[:5]:
                if isinstance(h, dict) and h.get("i_suspect"):
                    opinions.append(f"you suspect about {h.get('about')}: {_clip(h['i_suspect'], 200)}")
            opinion_block = "THE PEOPLE AROUND YOU, AS YOU SEE THEM:\n" + "\n".join(f"- {o}" for o in opinions[:14]) if opinions else ""
            under = told.get("undercurrent") if isinstance(told.get("undercurrent"), dict) else None
            calls.append({
                "capture": cap["id"], "chat": cap["chat_id"], "turn_idx": cap["idx"], "name": self_.get("name"),
                "tag": args.tag,
                "blocks": {"identity": identity, "perceived": perceived[:3500], "moods": mood_block,
                           "memories": memory_block[:3500], "opinions": opinion_block[:3000]},
                "told": {"surface": told["surface"].get("label"), "valence": told["surface"].get("valence"),
                         "arousal": told["surface"].get("arousal"),
                         "undercurrent": (under or {}).get("label"),
                         "under_valence": (under or {}).get("valence")}})
            past.append(_clip(told["surface"].get("label"), 120))
    rng = random.Random(7)
    if args.limit and len(calls) > args.limit:
        calls = sorted(rng.sample(calls, args.limit), key=lambda c: (c["chat"], c["turn_idx"], c["capture"]))
    Path(args.out).write_text(json.dumps(calls, indent=1), encoding="utf-8")
    print(f"{len(calls)} calls with a reported mood from chats {chats}")


def _state(call, arm):
    b = call["blocks"]
    parts = [b["identity"], b["perceived"]]
    if arm in ("B", "C", "D"):
        parts.append(b["moods"])
    if arm in ("C", "D"):
        parts.append(b["memories"])
    if arm == "D":
        parts.append(b["opinions"])
    return "\n\n".join(p for p in parts if p)


def _graded(question):
    return {"type": "choice", "instructions": question,
            "criteria": {k: label for k, (label, _w) in GRADE.items()}}


def _questions(kind):
    from mind.affect import _ling

    if kind in ("bases", "bases2"):
        qs = {f"base:{n}": _graded(text) for n, (text, _v, _a) in BASES.items()}
        for n, (text, options) in SPECTRUMS.items():
            qs[f"spec:{n}"] = {"type": "choice", "instructions": text,
                               "criteria": {f"s{i}": opt for i, opt in enumerate(options)}}
        if kind == "bases2":
            qs["under:strength"] = _graded(UNDER_STRENGTH)
            qs["under:kind"] = {"type": "choice", "instructions": UNDER_KIND,
                                "criteria": {**{n: n for n in BASES}, "none": "nothing in particular"}}
        return qs
    labels = list(_ling("AFFECT_LEXICON")) + list(EXTRA)
    return {f"label:{lab}": _graded(f"How much does '{lab}' describe how you feel right now?") for lab in labels}


def _read(answers, qs):
    out = {}
    for key, question in qs.items():
        probs = ((answers.get(key) or {}).get("probabilities") or {})
        if not probs:
            continue
        if key.startswith("spec:"):
            n = len(question["criteria"])
            out[key] = sum(float(probs.get(f"s{i}") or 0) * i / (n - 1) for i in range(n))
        elif key == "under:kind":
            for option in question["criteria"]:
                out[f"under:{option}"] = float(probs.get(option) or 0)
        else:
            out[key] = sum(float(probs.get(k) or 0) * w for k, (_l, w) in GRADE.items())
    return out


def ask(args):
    from llm import decisions

    calls = json.loads(Path(args.calls).read_text())
    out = Path(args.out)
    done = json.loads(out.read_text()) if out.exists() else {}
    jobs = []
    for call in calls:
        for arm in args.bases_arms.split(","):
            jobs.append((call, arm, args.bases_kind))
        jobs.append((call, "D", args.labels_kind))
    todo = [j for j in jobs if f"{j[0]['capture']}:{j[1]}:{j[2]}" not in done]

    def run(job):
        call, arm, kind = job
        qs = _questions(kind)
        answers = decisions.decide(_state(call, arm), qs)
        return f"{call['capture']}:{arm}:{kind}", _read(answers, qs)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, (key, grades) in enumerate(pool.map(run, todo), 1):
            done[key] = grades
            if n % 20 == 0 or n == len(todo):
                out.write_text(json.dumps(done), encoding="utf-8")
                print(f"{n} of {len(todo)} batteries")
    out.write_text(json.dumps(done), encoding="utf-8")
    (out.with_suffix(".calls.json")).write_text(json.dumps(calls), encoding="utf-8")


def describe_bases(g):
    """Code writes the mood from the grades: the named blend of the two
    strongest co-active bases, the strongest base's intensity name, and the
    spectrums in words."""
    bases = sorted(((g.get(f"base:{n}", 0.0), n) for n in BASES), reverse=True)
    active = [(v, n) for v, n in bases if v >= 0.5]
    words = []
    if active:
        v0, n0 = active[0]
        words.append(INTENSITY[n0][0 if v0 < 0.6 else 1 if v0 < 0.85 else 2])
        if len(active) > 1:
            blend = DYADS.get(frozenset((n0, active[1][1])))
            words.append(f"{blend} ({n0} with {active[1][1]})" if blend else f"with {INTENSITY[active[1][1]][1]}")
        for v, n in active[2:4]:
            words.append(f"some {INTENSITY[n][0]}")
    else:
        words.append("no strong feeling")
    spec = {n: g.get(f"spec:{n}") for n in SPECTRUMS}
    poles = {"pleasure": ("unpleasant", "pleasant"), "arousal": ("calm", "stirred up"),
             "dominance": ("powerless", "in control"), "playful": ("serious", "playful"),
             "open": ("guarded", "open")}
    for n, (lo, hi) in poles.items():
        if spec.get(n) is not None and abs(spec[n] - 0.5) >= 0.2:
            words.append(hi if spec[n] > 0.5 else lo)
    return ", ".join(words)


def describe_labels(g, k=3):
    top = sorted(((v, key.split(":", 1)[1]) for key, v in g.items() if key.startswith("label:")), reverse=True)[:k]
    return ", ".join(lab for _v, lab in top)


def match(args):
    """Does each description name the same feeling as the character's own
    words? By meaning, on the configured embedder: the cosine between the
    character's words and each description, against a shuffled control -- the
    same method's description of a different call. No model is asked."""
    import numpy as np

    from llm.providers import embed_texts_meta

    moods = json.loads(Path(args.moods).read_text())
    calls = json.loads(Path(args.moods).with_suffix(".calls.json").read_text())
    rng = random.Random(11)
    shuffled = calls[:]
    while any(a["capture"] == b["capture"] for a, b in zip(calls, shuffled)):
        rng.shuffle(shuffled)
    rows = []
    for call, other in zip(calls, shuffled):
        told = call["told"]["surface"] + (
            f"; beneath it, {call['told']['undercurrent']}" if call["told"].get("undercurrent") else "")
        for name, fn in (("bases", describe_bases), ("labels", describe_labels)):
            mine = moods.get(f"{call['capture']}:D:{name}")
            theirs = moods.get(f"{other['capture']}:D:{name}")
            if mine and theirs:
                rows.append({"capture": call["capture"], "method": name, "told": told,
                             "desc": fn(mine), "control": fn(theirs)})
    texts = sorted({t for r in rows for t in (r["told"], r["desc"], r["control"])})
    vec = dict(zip(texts, embed_texts_meta(texts).vectors))
    for r in rows:
        r["match"] = float(np.dot(vec[r["told"]], vec[r["desc"]]))
        r["control_match"] = float(np.dot(vec[r["told"]], vec[r["control"]]))
    Path(args.moods).with_suffix(".matched.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"{len(rows)} descriptions matched by meaning")


REFERENCE_SYSTEM = ("For each numbered description of how a character feels, answer whether it "
                    "describes sexual or romantic desire or arousal. Return JSON only: "
                    "{\"answers\": {\"R1\": \"yes\", \"R2\": \"no\", ...}} with every id.")


def reference(args):
    """Mark each call whose own reported mood (surface or undercurrent)
    describes sexual or romantic desire -- the reference the intimate labels
    and the desire base are scored against. Read by the `utility` model on the
    character's words alone; Jev's answers are not shown to it."""
    from agents.common import jparse
    from llm.providers import chat_complete

    path = Path(args.calls)
    calls = json.loads(path.read_text())
    todo = [c for c in calls if "intimate_ref" not in c]
    for start in range(0, len(todo), 30):
        chunk = todo[start:start + 30]
        user = "\n".join(f"R{i + 1}: {c['told']['surface']}"
                          + (f"; beneath it, {c['told']['undercurrent']}" if c["told"].get("undercurrent") else "")
                          for i, c in enumerate(chunk))
        reply = jparse(chat_complete("utility", REFERENCE_SYSTEM, user, json_mode=True, temperature=0.0,
                                     max_tokens=1500, reasoning_effort="off")) or {}
        answers = reply.get("answers") or {}
        for i, c in enumerate(chunk):
            a = str(answers.get(f"R{i + 1}") or "").strip().lower()
            if a in ("yes", "no"):
                c["intimate_ref"] = a == "yes"
        path.write_text(json.dumps(calls, indent=1), encoding="utf-8")
    print(f"{sum(1 for c in calls if c.get('intimate_ref'))} of {len(calls)} calls report sexual or romantic desire")


def score(args):
    import numpy as np

    from mind.affect import _ling

    moods = json.loads(Path(args.moods).read_text())
    calls = json.loads(Path(args.calls).read_text()) if args.calls else \
        json.loads(Path(args.moods).with_suffix(".calls.json").read_text())
    if args.tag:
        calls = [c for c in calls if c.get("tag") == args.tag]
    lexicon = {lab: (e.get("v", 0), e.get("a", 0)) for lab, e in _ling("AFFECT_LEXICON").items()}
    signs = {**lexicon, **EXTRA, **LEGACY}
    bk, lk = args.bases_kind, args.labels_kind

    def r(x, y):
        return float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 and np.std(x) > 0 and np.std(y) > 0 else float("nan")

    def base_valence(g):
        w = [(g.get(f"base:{n}", 0.0), v) for n, (_t, v, _a) in BASES.items()]
        tot = sum(x for x, _ in w)
        return sum(x * v for x, v in w) / tot if tot else 0.0

    told_v = np.array([float(c["told"]["valence"] or 0) for c in calls])
    told_a = np.array([float(c["told"]["arousal"] or 0) for c in calls])
    print(f"{len(calls)} calls ({args.tag or 'all'}), {len({(c['chat'], c['turn_idx']) for c in calls})} beats; "
          f"characters {sorted({c['name'] for c in calls})}")
    print(f"  {bk} by context: valence r (spectrum / from bases), valence sign, arousal r, bases >= clearly")
    for arm in ARMS:
        gs = [moods.get(f"{c['capture']}:{arm}:{bk}") for c in calls]
        if not all(gs):
            continue
        v_spec = np.array([g.get("spec:pleasure", 0.5) * 2 - 1 for g in gs])
        v_base = np.array([base_valence(g) for g in gs])
        a_spec = np.array([g.get("spec:arousal", 0.5) for g in gs])
        multi = np.mean([sum(1 for n in BASES if g.get(f"base:{n}", 0) >= 2 / 3) for g in gs])
        print(f"    {arm}: {r(v_spec, told_v):5.2f} / {r(v_base, told_v):5.2f}   "
              f"{np.mean(np.sign(v_spec) == np.sign(told_v)):4.0%}   {r(a_spec, told_a):5.2f}   {multi:4.1f}")
    gl = [moods.get(f"{c['capture']}:D:{lk}") for c in calls]
    if all(gl):
        def label_va(g):
            w = [(v, signs[key.split(":", 1)[1]]) for key, v in g.items()
                 if key.startswith("label:") and key.split(":", 1)[1] in signs]
            tot = sum(x for x, _ in w)
            return (sum(x * s_[0] for x, s_ in w) / tot, sum(x * s_[1] for x, s_ in w) / tot) if tot else (0, 0)
        va = np.array([label_va(g) for g in gl])
        print(f"  {lk} at D: valence r {r(va[:, 0], told_v):.2f}, sign {np.mean(np.sign(va[:, 0]) == np.sign(told_v)):.0%}, "
              f"arousal r {r(va[:, 1], told_a):.2f}, labels >= clearly {np.mean([sum(1 for v in g.values() if v >= 2 / 3) for g in gl]):.1f}")
    gd = [moods.get(f"{c['capture']}:D:{bk}") for c in calls]
    if all(gd) and all("under:strength" in g for g in gd):
        told_u = [c for c, g in zip(calls, gd) if c["told"].get("undercurrent")]
        det = [g["under:strength"] >= 1 / 3 for c, g in zip(calls, gd) if c["told"].get("undercurrent")]
        neg_told = [(c, g) for c, g in zip(calls, gd) if (c["told"].get("under_valence") or 0) < 0]
        neg_kind = [sum(g.get(f"under:{n}", 0) for n in ("fear", "sadness", "anger", "disgust")) > 0.5 for _c, g in neg_told]
        print(f"  undercurrent: the character reported one on {len(told_u)}; Jev found one (>= slightly) on "
              f"{sum(det)}; of {len(neg_told)} negative ones, Jev's quieter feeling was negative on {sum(neg_kind)}")
    if all("intimate_ref" in c for c in calls) and all(gd) and all(gl):
        ref = np.array([c["intimate_ref"] for c in calls])
        for name, pred in (("desire base >= clearly", np.array([g.get("base:desire", 0) >= 2 / 3 for g in gd])),
                           ("desire base >= slightly", np.array([g.get("base:desire", 0) >= 1 / 3 for g in gd])),
                           ("an intimate label >= clearly", np.array([any(g.get(f"label:{lab}", 0) >= 2 / 3 for lab in INTIMATE) for g in gl]))):
            tp, fp, fn = int((pred & ref).sum()), int((pred & ~ref).sum()), int((~pred & ref).sum())
            print(f"  intimate, {name:30} precision {tp / max(1, tp + fp):.0%} recall {tp / max(1, tp + fn):.0%} "
                  f"(reference yes on {int(ref.sum())} of {len(ref)})")
    if args.show:
        for c in calls[:args.show]:
            gb = moods.get(f"{c['capture']}:D:{bk}") or {}
            g2 = moods.get(f"{c['capture']}:D:{lk}") or {}
            under = ""
            if "under:strength" in gb and gb["under:strength"] >= 1 / 3:
                kind = max(BASES, key=lambda n: gb.get(f"under:{n}", 0))
                under = f"; beneath: {INTENSITY[kind][0]}"
            print(f"\n  chat {c['chat']} idx {c['turn_idx']} {c['name']}\n    told:   {c['told']['surface']}"
                  f" | beneath: {c['told'].get('undercurrent')}\n    bases:  {describe_bases(gb)}{under}"
                  f"\n    labels: {describe_labels(g2)}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("collect")
    p.add_argument("--chats", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=80)
    p.add_argument("--per-beat", action="store_true", help="only the first call of each beat")
    p.add_argument("--tag", default="")
    p = sub.add_parser("ask")
    p.add_argument("--calls", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--bases-kind", default="bases")
    p.add_argument("--bases-arms", default="A,B,C,D")
    p.add_argument("--labels-kind", default="labels")
    p = sub.add_parser("match")
    p.add_argument("--moods", required=True)
    p = sub.add_parser("reference")
    p.add_argument("--calls", required=True)
    p = sub.add_parser("score")
    p.add_argument("--moods", required=True)
    p.add_argument("--calls", default="")
    p.add_argument("--tag", default="")
    p.add_argument("--bases-kind", default="bases")
    p.add_argument("--labels-kind", default="labels")
    p.add_argument("--show", type=int, default=0)
    args = parser.parse_args()
    {"collect": collect, "ask": ask, "match": match, "reference": reference, "score": score}[args.mode](args)


if __name__ == "__main__":
    main()
