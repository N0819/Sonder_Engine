"""Decision-model training data: one example a (state, question) (2026-10-06).

The owner: "The best option would probably be to finetune a small decision
model maybe 4 or 9b parameters specifically for sonder. but for now using jev
is fine." Then: "I suppose we might as well build a training data file for the
day we decide to do a fine tune." This builds that file.

A decision model answers typed QUESTIONS against a STATE, every question on
its own (`llm/decisions.py`), so the unit of training is one (state, question)
pair and its answer. An example carries up to two answers:

- TEACHER: what the decision model the engine runs today answered -- in Jev's
  own answer shape, averaged over every time the engine asked the same
  question of the same state, with that count. From the request files
  `decisions.capture` writes beside each database while the
  `decision_capture` setting is on (`training/decisions/<database>/<day>.jsonl`;
  the settings panel's "Keep decision-model training data").
- GOLD: the option that is right, known without any model --
  - the router's labelled questions (`tools/chrono_bench/router_tuning.json`
    and `router_heldout.json`), built here by the engine's own question
    builders (`memory_routes.route_questions`, `question_state`): every route
    question the item's labels decide. The held-out set is always `eval`.
  - the concept lab's large bank (`tools/concept_lab/bank_large.json`): who
    is physically present in each of 240 memories, its best-audited label
    (four blind relabellings, persons agreeing at 0.94, 178 disputes ruled),
    as `character_jev.memory_met` -- every present person yes, every person
    the memory mentions but who is not there no (the hard case), and one
    person it never mentions no;
  - the Saltmere bank's planted moments (`tools/chrono_bench/questions.json`
    over `bank.json`), attached to the moment checks a bench run captured
    (`character_jev.memory_met`, `memory_moment`, `memory_heard`,
    `memory_anchor`): yes for the planted episode; no for a row on the far side
    of it, which the adversarial readers checked holds no instance (before a
    planted first, after a planted last, anywhere for a question nothing in
    the bank answers). Everything else stays unlabelled -- a later instance of
    a first time is still an instance, and an inference written the same beat
    may only think back on it.

    python tools/decision_data/build.py [--captures PATH ...] [--no-install-captures]
                                        [--out PATH] [--summary]

`--captures` adds request files or folders (a folder is read recursively,
`.jsonl` and `.jsonl.gz`); the install's own `training/decisions/` is read
unless `--no-install-captures`, and the committed seed
(`tools/decision_data/seed_examples.jsonl`, the gold examples the benches
paid for) unless `--no-seed`. Blind rulings (`rulings.json`) correct or drop
the gold labels three judges disputed. The output defaults to
`training/decision_examples.jsonl` beside the install's database. Captures
from real chats carry their story text into it: the file stays on the machine.

The format is documented in `docs/guides/DECISION_TRAINING_DATA.md`.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCH = ROOT / "tools" / "chrono_bench"
#: What the benches paid for, kept in the repo: every example a bench run
#: captured that has a gold label, with the teacher's answer. Every build reads
#: it, so the training file always holds them; `--gold-only --captured-only`
#: writes it (it is read first, so it grows rather than being replaced).
SEED = HERE / "seed_examples.jsonl"
#: Blind rulings on the gold labels the teacher disagreed with, by example id:
#: `keep`, `relabel` (three judges of three against the label) or `drop` (two
#: of three) -- `rulings.json`'s own note says how they were made.
RULINGS = HERE / "rulings.json"
#: The share of a group's examples held out for evaluation: a group (a story
#: frame, a Saltmere question) goes whole to one side, so no state is read in
#: training and graded in evaluation.
EVAL_SHARE = 10  # percent
#: The moment checks the Saltmere labels can grade, by the card's own names.
MOMENT_TASKS = {"character_jev.memory_met", "character_jev.memory_moment",
                "character_jev.memory_heard", "character_jev.memory_anchor"}
#: `questions.json` names the kinds as the bank's bible did; the router's own
#: are `memory_routes.KINDS`.
KIND_ALIASES = {"said_or_did": "act"}
#: A template's literal opening must be at least this long to name a task by
#: prefix -- shorter ones ("{memory}") would claim everything.
MIN_PREFIX = 12
_STATE_QUESTION = re.compile(r"^(?:(?P<asker>.+?) ASKED YOU|THE QUESTION YOU ARE ASKING YOUR OWN MEMORY): (?P<q>.*)$",
                             re.S)
_MEMORY_LINE = re.compile(r"^MEMORY \((?P<when>.*?)\): (?P<body>.*)$")


def _norm(text):
    return " ".join(str(text or "").split())


def example_id(state, question):
    blob = (state if isinstance(state, str) else json.dumps(state, sort_keys=True, ensure_ascii=False)) \
        + "\x1f" + json.dumps(question, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:20]


def _split(group):
    return "eval" if int(hashlib.sha1(str(group).encode("utf-8")).hexdigest()[:8], 16) % 100 < EVAL_SHARE \
        else "train"


# --- tasks: which card question an instruction came from ------------------------------------

class Tasks:
    """Names an instruction by the card text it was filled from
    (`character_jev.memory_met`), the longest literal opening that fits; a
    question no card text opens is named by its key with the numbers taken out
    (`key:moment:#`)."""

    def __init__(self, languages):
        from language_runtime import language_pack
        self._by_head = defaultdict(list)
        for language in languages:
            try:
                card = language_pack(language).card("system_prompts")
            except Exception:  # noqa: BLE001 -- a pack that will not load names nothing
                continue
            self._walk(card, [])
        for heads in self._by_head.values():
            heads.sort(key=lambda t: -len(t[0]))

    def _walk(self, node, path):
        if isinstance(node, Mapping):  # a pack's card is a read-only mappingproxy
            for key, value in node.items():
                self._walk(value, path + [str(key)])
        elif isinstance(node, str):
            cut = node.find("{")
            head = node if cut < 0 else node[:cut]
            if len(head) >= MIN_PREFIX:
                self._by_head[head[:MIN_PREFIX]].append((head, ".".join(path), cut < 0))

    def name(self, instructions, key):
        text = str(instructions or "")
        for head, path, whole in self._by_head.get(text[:MIN_PREFIX], ()):
            if (text == head) if whole else text.startswith(head):
                return path
        return "key:" + re.sub(r"\d+", "#", str(key))


# --- teacher answers --------------------------------------------------------------------------

def _teacher_add(acc, answer):
    """Fold one of Jev's answers into a running sum, by its own shape."""
    if not isinstance(answer, dict):
        return
    acc["n"] = acc.get("n", 0) + 1
    if isinstance(answer.get("probabilities"), dict):
        sums = acc.setdefault("probabilities", {})
        for option, p in answer["probabilities"].items():
            try:
                sums[str(option)] = sums.get(str(option), 0.0) + float(p)
            except (TypeError, ValueError):
                continue
    elif answer.get("choice") is not None:
        sums = acc.setdefault("probabilities", {})
        sums[str(answer["choice"])] = sums.get(str(answer["choice"]), 0.0) + 1.0
    for field in ("noul", "score", "confidence"):
        if isinstance(answer.get(field), (int, float)):
            acc.setdefault(field, 0.0)
            acc[field] += float(answer[field])
            acc.setdefault("_n_" + field, 0)
            acc["_n_" + field] += 1


def _teacher_merge(acc, teacher):
    """Fold an averaged teacher answer, with its count, into a running sum."""
    if not isinstance(teacher, dict):
        return
    n = int(teacher.get("n") or 1)
    acc["n"] = acc.get("n", 0) + n
    if isinstance(teacher.get("probabilities"), dict):
        sums = acc.setdefault("probabilities", {})
        for option, p in teacher["probabilities"].items():
            sums[str(option)] = sums.get(str(option), 0.0) + float(p) * n
    for field in ("noul", "score", "confidence"):
        if isinstance(teacher.get(field), (int, float)):
            acc[field] = acc.get(field, 0.0) + float(teacher[field]) * n
            acc["_n_" + field] = acc.get("_n_" + field, 0) + n


def read_examples(path):
    """A built file's examples (the seed, or a previous build)."""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _teacher_out(acc, kind):
    if not acc or not acc.get("n"):
        return None
    n = acc["n"]
    out = {"type": kind}
    if "probabilities" in acc:
        probs = {k: round(v / n, 4) for k, v in acc["probabilities"].items()}
        out["probabilities"] = probs
        out["choice"] = max(probs, key=probs.get) if probs else None
    for field in ("noul", "score", "confidence"):
        if field in acc:
            out[field] = round(acc[field] / max(1, acc["_n_" + field]), 4)
    return out


# --- captures ---------------------------------------------------------------------------------

def capture_files(paths):
    out = []
    for path in paths:
        p = Path(path)
        if p.is_dir():
            out.extend(sorted(x for x in p.rglob("*") if x.name.endswith((".jsonl", ".jsonl.gz"))))
        elif p.exists():
            out.append(p)
    return out


def read_capture(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue  # a line cut off by a crash mid-write


# --- gold: the router -------------------------------------------------------------------------

def router_gold(path, split=None):
    """Every route question an item's labels decide, built as the engine
    builds it. `split` forces a side (the held-out set is `eval`)."""
    from mind.memory import question_state, route_questions
    name = f"chrono_bench/{Path(path).name}"
    for n, item in enumerate(json.loads(Path(path).read_text(encoding="utf-8"))):
        people = list(dict.fromkeys(str(p) for p in item.get("people") or [] if str(p or "").strip()))
        asker = item.get("asker") or None
        language = item.get("lang") or "en"
        state = question_state(item["question"], asker)
        questions = route_questions(people, language, asker)
        orders = list(item.get("ok_order") or [])
        chrono = bool(orders) and "content" not in orders
        accept = {"route:order": orders}
        if chrono and item.get("ok_kind"):
            accept["route:kind"] = list(item["ok_kind"])
        if chrono:
            accept["route:past"] = ["yes"]
        if "route:who" in questions:
            who = item.get("who")
            if who and who in people:
                accept["route:who"] = [f"p{people.index(who)}"]
            elif not who:
                accept["route:who"] = ["none"]
        for key, options in accept.items():
            if not options:
                continue
            yield {"state": state, "question": questions[key], "key": key, "language": language,
                   "gold": {"accept": options, "source": f"{name}#{n}"},
                   "group": name, "split": split}


# --- gold: the concept lab's people present ---------------------------------------------------

def concept_lab_met(path=ROOT / "tools" / "concept_lab" / "bank_large.json"):
    """`memory_met` for each memory and person, built as the routed ponder
    asks it: the memory as `memory_line` renders it at the verifier's length
    (who was in it included), the person by name, a first-meeting question as
    the state."""
    from llm.prompts import character_jev_options, character_jev_text
    from mind.affect_appraisal import _fill
    from mind.memory import VERIFY_CHARS, memory_line, question_state
    bank = json.loads(Path(path).read_text(encoding="utf-8"))
    persons = {c["id"]: c["name"] for c in bank["concepts"] if c.get("kind") == "person"}
    known = {n.casefold() for n in persons.values()}
    now = max(m["turn"] for m in bank["memories"]) + 1
    text, yesno = character_jev_text("memory_met", "en"), dict(character_jev_options("yesno", "en"))
    name = f"concept_lab/{Path(path).name}"
    for m in bank["memories"]:
        present = [p for p in m.get("about") or [] if p in persons]
        mentioned = [p for p in m.get("concepts") or [] if p in persons and p not in present]
        absent = sorted(p for p in persons if p not in present and p not in mentioned)
        asked = [(p, "yes") for p in present] + [(p, "no") for p in mentioned]
        if absent:
            pick = int(hashlib.sha1(m["id"].encode("utf-8")).hexdigest()[:8], 16) % len(absent)
            asked.append((absent[pick], "no"))
        mem = {"content": f"What I experienced: {m['experienced']} What I did: {m['did']}",
               "turn_idx": m["turn"], "about": [persons[p] for p in present]}
        line = memory_line(mem, now, known, chars=VERIFY_CHARS)
        for pid, answer in asked:
            question = {"type": "choice", "instructions": _fill(text, {"memory": line, "person": persons[pid]}),
                        "criteria": dict(yesno)}
            yield {"state": question_state(f"When did I first meet {persons[pid]}?"), "question": question,
                   "key": "moment:met", "language": "en",
                   "gold": {"accept": [answer], "source": f"{name}#{m['id']}:{pid}"},
                   "group": f"{name}#{m['id']}", "split": None}


# --- gold: Saltmere's planted moments ---------------------------------------------------------

class Saltmere:
    """Labels the moment checks a Saltmere bench run captured."""

    def __init__(self, bench=BENCH):
        self.questions = {}
        doc = json.loads((Path(bench) / "questions.json").read_text(encoding="utf-8"))
        for q in doc["questions"]:
            for text in (q.get("en"), q.get("ja")):
                if text:
                    self.questions[_norm(text)] = q
        bank = json.loads((Path(bench) / "bank.json").read_text(encoding="utf-8"))
        self.rows = {}
        for t in bank["turns"]:
            self.rows.setdefault(_norm(t["content"])[:1500], (t["turn"], "episode"))
            for inf in t.get("inferences") or []:
                self.rows.setdefault(_norm(inf.get("text"))[:1500], (t["turn"], "inference"))
        for p in bank["past"]:
            self.rows.setdefault(_norm(p["content"])[:1500], ("past", "past"))

    def _row(self, instructions):
        line = str(instructions or "").rsplit("\n", 1)[-1]
        m = _MEMORY_LINE.match(line)
        if not m:
            return None
        body = m.group("body")
        hit = self.rows.get(body)
        if hit is None:
            # `memory_line` cuts to the caller's length; a shorter cut is a prefix
            hit = next((v for k, v in self.rows.items() if k.startswith(body) and len(body) >= 200), None)
        return hit

    def question_of(self, state):
        """The bank question a state asks, or None."""
        m = _STATE_QUESTION.match(state) if isinstance(state, str) else None
        return self.questions.get(_norm(m.group("q"))) if m else None

    def label(self, state, task, instructions):
        """`(accept, source)` or None."""
        if task not in MOMENT_TASKS:
            return None
        q = self.question_of(state)
        row = self._row(instructions) if q else None
        if not q or not row:
            return None
        turn, kind = row
        source = f"chrono_bench/questions.json#{q['id']}"
        order, qkind = q.get("order"), KIND_ALIASES.get(q.get("kind"), q.get("kind"))
        want = q.get("answer_turns") or []
        if any(not isinstance(w, int) for w in want):
            return None  # an answer in the seeded past: which row is not recorded
        short = task.rsplit(".", 1)[-1]
        if order in ("before", "after"):
            if short != "memory_anchor" or not isinstance(q.get("moment_turn"), int) or q["moment_turn"] < 0:
                return None
            if kind == "episode" and turn == q["moment_turn"]:
                return ["yes"], source
            return None
        if order not in ("earliest", "latest") or short == "memory_anchor":
            return None
        fits = {"met": {"memory_met", "memory_moment"}, "heard_of": {"memory_heard", "memory_moment"},
                "place": {"memory_moment"}, "act": {"memory_moment"}}.get(qkind, set())
        if short not in fits:
            return None
        if not want:
            return (["no"], source) if short != "memory_heard" else None
        if kind == "episode" and turn in want:
            return ["yes"], source
        if turn == "past":
            return (["no"], source) if order == "earliest" else None
        if order == "earliest" and turn < min(want):
            return ["no"], source
        if order == "latest" and turn > max(want):
            return ["no"], source
        return None


# --- the build --------------------------------------------------------------------------------

def _database_path():
    """The install's database as `core/db.py` will resolve it, read without
    importing it: importing the engine opens it."""
    return Path(os.path.abspath(os.environ.get("ENGINE_DB") or ROOT / "engine.db"))


def build(capture_paths, *, gold_router=True, saltmere=True, concept_lab=True, seed=SEED, rulings=RULINGS):
    """`{id: example}` from the seed, the captures and the gold sources, with
    the judges' rulings applied. `seed` and `rulings` are paths, or None."""
    examples = {}
    teachers = defaultdict(dict)
    files = capture_files(capture_paths)
    languages = {"en", "ja"}
    requests = []
    for path in files:
        for rec in read_capture(path):
            requests.append((path, rec))
            if rec.get("language"):
                languages.add(str(rec["language"]))
    tasks = Tasks(sorted(languages))
    labeller = Saltmere() if saltmere else None

    def put(state, question, key, language, *, source=None, step=None, group=None, split=None,
            gold=None, answer=None, model=None):
        eid = example_id(state, question)
        ex = examples.get(eid)
        if ex is None:
            ex = examples[eid] = {
                "id": eid, "task": tasks.name(question.get("instructions"), key), "key": key,
                "language": language or "en", "state": state, "question": question,
                "teacher": None, "gold": None, "split": split, "group": group,
                "sources": [], "steps": [], "models": []}
        if split and not ex["split"]:
            ex["split"] = split
        if group and not ex["group"]:
            ex["group"] = group
        if source and source not in ex["sources"]:
            ex["sources"].append(source)
        if step and step not in ex["steps"]:
            ex["steps"].append(step)
        if model and model not in ex["models"]:
            ex["models"].append(model)
        if gold and not ex["gold"]:
            ex["gold"] = gold
        if answer is not None:
            _teacher_add(teachers[eid], answer)
        return ex

    if gold_router:
        # The tuning set is what the router's wording was chosen on, so it is
        # never evidence for a model: train. The held-out set never steered
        # anything: eval.
        for name, split in (("router_tuning.json", "train"), ("router_heldout.json", "eval")):
            path = BENCH / name
            if path.exists():
                for g in router_gold(path, split):
                    put(g["state"], g["question"], g["key"], g["language"], source=g["gold"]["source"],
                        group=g["group"], split=g["split"], gold=g["gold"])

    if concept_lab:
        for g in concept_lab_met():
            put(g["state"], g["question"], g["key"], g["language"], source=g["gold"]["source"],
                group=g["group"], gold=g["gold"])

    if seed and Path(seed).exists():
        for old in read_examples(seed):
            ex = put(old["state"], old["question"], old.get("key"), old.get("language"),
                     group=old.get("group"), gold=old.get("gold"))
            for field in ("sources", "steps", "models"):
                for value in old.get(field) or []:
                    if value not in ex[field]:
                        ex[field].append(value)
            _teacher_merge(teachers[ex["id"]], old.get("teacher"))

    for path, rec in requests:
        state, language = rec.get("state"), rec.get("language") or "en"
        answers = rec.get("answers") or {}
        where = f"capture:{path.parent.name}/{path.name}"
        frame = rec.get("frame")
        # A bench question's every request is one group, labelled or not: its
        # moment checks, its router questions and its graded ponder share the
        # question, so they go to one side together.
        asked = labeller.question_of(state) if labeller else None
        group = f"chrono_bench/questions.json#{asked['id']}" if asked else (
            f"{path.parent.name}:frame:{frame}" if frame is not None else f"state:{example_id(state, {})}")
        for key, question in (rec.get("questions") or {}).items():
            if not isinstance(question, dict):
                continue
            ex = put(state, question, key, language, source=where, step=rec.get("step"), group=group,
                     answer=answers.get(key), model=rec.get("model"))
            if labeller and not ex["gold"]:
                hit = labeller.label(state, ex["task"], question.get("instructions"))
                if hit:
                    accept, source = hit
                    ex["gold"] = {"accept": accept, "source": source}

    if rulings and Path(rulings).exists():
        for eid, ruling in json.loads(Path(rulings).read_text(encoding="utf-8"))["rulings"].items():
            ex = examples.get(eid)
            if not ex or not ex["gold"]:
                continue
            if ruling["ruling"] == "drop":
                ex["gold"] = None
            else:
                ex["gold"] = {**ex["gold"], "ruled": ruling["votes"]}
                if ruling["ruling"] == "relabel":
                    ex["gold"]["accept"] = list(ruling["accept"])

    # One state, one side: a split a source fixes (the router's held-out set
    # is eval, its tuning set train) holds for every example of that state,
    # eval winning a conflict; the rest go by their group.
    fixed = {}
    for ex in examples.values():
        if ex["split"]:
            key = example_id(ex["state"], {})
            fixed[key] = "eval" if "eval" in (fixed.get(key), ex["split"]) else ex["split"]
    for eid, ex in examples.items():
        ex["teacher"] = _teacher_out(teachers.get(eid), ex["question"].get("type"))
        if ex["teacher"]:
            ex["teacher"]["n"] = teachers[eid]["n"]
        ex["split"] = fixed.get(example_id(ex["state"], {})) or _split(ex["group"])
    return examples


def summary(examples):
    by_task = defaultdict(Counter)
    for ex in examples.values():
        c = by_task[ex["task"]]
        c["examples"] += 1
        c["gold"] += bool(ex["gold"])
        c["teacher"] += bool(ex["teacher"])
        c["both"] += bool(ex["gold"] and ex["teacher"])
        c["ruled"] += bool(ex["gold"] and ex["gold"].get("ruled"))
        c[ex["split"]] += 1
        if ex["gold"] and ex["teacher"] and ex["teacher"].get("choice") is not None:
            c["teacher_right"] += ex["teacher"]["choice"] in ex["gold"]["accept"]
    return {"examples": len(examples),
            "gold": sum(1 for e in examples.values() if e["gold"]),
            "teacher": sum(1 for e in examples.values() if e["teacher"]),
            "languages": dict(Counter(e["language"] for e in examples.values())),
            "splits": dict(Counter(e["split"] for e in examples.values())),
            "by_task": {k: dict(v) for k, v in sorted(by_task.items())}}


def write(examples, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    order = sorted(examples.values(), key=lambda e: (e["split"], e["task"], e["id"]))
    tmp = out.with_suffix(out.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for ex in order:
            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
    os.replace(tmp, out)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--captures", nargs="*", default=[], help="request files or folders")
    parser.add_argument("--no-install-captures", action="store_true",
                        help="leave out training/decisions beside the install's database")
    parser.add_argument("--out", default=None, help="default: training/decision_examples.jsonl")
    parser.add_argument("--summary", action="store_true", help="print counts, write nothing")
    parser.add_argument("--gold-only", action="store_true", help="write only examples with a gold label")
    parser.add_argument("--captured-only", action="store_true",
                        help="write only examples some capture asked (what a bench run paid for)")
    parser.add_argument("--no-seed", action="store_true", help="leave out the committed seed")
    args = parser.parse_args(argv)
    database = _database_path()
    home = database.parent
    scratch = None
    if not database.exists():
        # Importing the engine reads a setting (`core/logging_utils`), and
        # SQLite creates the file it is asked to read: a checkout with no
        # database would be left holding an empty one.
        handle, scratch = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        os.environ["ENGINE_DB"] = scratch
    try:
        paths = list(args.captures)
        if not args.no_install_captures:
            paths.append(str(home / "training" / "decisions"))
        examples = build(paths, seed=None if args.no_seed else SEED)
        if args.gold_only:
            examples = {k: v for k, v in examples.items() if v["gold"]}
        if args.captured_only:
            examples = {k: v for k, v in examples.items()
                        if any(str(x).startswith("capture:") for x in v["sources"])}
        info = summary(examples)
        if not args.summary:
            info["written"] = str(write(examples, args.out or home / "training" / "decision_examples.jsonl"))
        print(json.dumps(info, ensure_ascii=False, indent=1))
    finally:
        if scratch:
            for path in (scratch, scratch + "-wal", scratch + "-shm"):
                if os.path.exists(path):
                    os.remove(path)


if __name__ == "__main__":
    main()
