"""The decision-model training file (`tools/decision_data/build.py`).

Pinned here: a captured request becomes one example a question, repeats of one
(state, question) are averaged into one teacher answer with their count; the
router's labelled sets become gold examples built by the engine's own question
builders, the held-out set always `eval`; a Saltmere moment check is labelled
yes only for the planted episode and no only on the checked side of it, and an
inference written the same beat stays unlabelled; a group goes whole to one
split; the committed seed merges in by its teacher count; and the judges'
rulings keep, relabel or drop a disputed label.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_decision_data_build", ROOT / "tools" / "decision_data" / "build.py")
build = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("_decision_data_build", build)
_spec.loader.exec_module(build)

ASK_AT = 312


def _bank():
    return json.loads((ROOT / "tools" / "chrono_bench" / "bank.json").read_text(encoding="utf-8"))


def _questions():
    return {q["id"]: q for q in json.loads(
        (ROOT / "tools" / "chrono_bench" / "questions.json").read_text(encoding="utf-8"))["questions"]}


def _moment(task, memory_body, turn, text_language="en"):
    from llm.prompts import character_jev_options, character_jev_text
    from mind.affect_appraisal import _fill
    line = f"MEMORY ({ASK_AT - turn} beats ago): {' '.join(memory_body.split())[:1500]}"
    return {"type": "choice", "instructions": _fill(character_jev_text(task, text_language),
                                                    {"memory": line, "person": "Oren Dask"}),
            "criteria": dict(character_jev_options("yesno", text_language))}


def _capture(tmp_path, records, name="saltmere_on"):
    folder = tmp_path / "captures" / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "2026-10-06.jsonl"
    with open(path, "a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return tmp_path / "captures"


def _yes(p):
    return {"type": "choice", "choice": "yes" if p >= 0.5 else "no", "probabilities": {"yes": p, "no": 1 - p}}


def test_a_request_is_one_example_a_question_and_repeats_average(tmp_path):
    q = {"type": "choice", "instructions": "Is it raining in this scene?", "criteria": {"yes": "Yes.", "no": "No."}}
    n = {"type": "noul", "instructions": "Does anyone speak?"}
    rec = {"model": "jev", "frame": 3, "step": "character:7", "language": "en", "state": "RAIN ON THE ROOF",
           "questions": {"a": q, "b": n}, "answers": {"a": _yes(0.8), "b": {"type": "noul", "noul": 0.2}}}
    again = dict(rec, answers={"a": _yes(0.6), "b": {"type": "noul", "noul": 0.4}})
    ex = build.build([str(_capture(tmp_path, [rec, again]))], gold_router=False, saltmere=False, concept_lab=False, seed=None,
                      rulings=None)
    assert len(ex) == 2
    a = ex[build.example_id("RAIN ON THE ROOF", q)]
    assert a["teacher"]["probabilities"] == {"yes": 0.7, "no": 0.3} and a["teacher"]["n"] == 2
    assert a["teacher"]["choice"] == "yes" and a["gold"] is None
    assert a["steps"] == ["character:7"] and a["models"] == ["jev"]
    b = ex[build.example_id("RAIN ON THE ROOF", n)]
    assert b["teacher"]["noul"] == 0.3 and b["teacher"]["type"] == "noul"
    assert a["group"] == b["group"] == "saltmere_on:frame:3" and a["split"] == b["split"]


def test_the_router_sets_become_gold_built_as_the_engine_builds_them():
    from mind.memory import question_state, route_questions
    ex = build.build([], saltmere=False, concept_lab=False, seed=None, rulings=None)
    items = json.loads((ROOT / "tools" / "chrono_bench" / "router_heldout.json").read_text(encoding="utf-8"))
    it = next(i for i in items if i["asker"] and i.get("who") and i["who"] != i["asker"]
              and "content" not in i["ok_order"])
    people = list(dict.fromkeys(it["people"]))
    qs = route_questions(people, it["lang"], it["asker"])
    state = question_state(it["question"], it["asker"])
    order = ex[build.example_id(state, qs["route:order"])]
    assert order["gold"]["accept"] == it["ok_order"] and order["split"] == "eval"
    assert order["task"] == "character_jev.route_order"
    assert ex[build.example_id(state, qs["route:past"])]["gold"]["accept"] == ["yes"]
    assert ex[build.example_id(state, qs["route:who"])]["gold"]["accept"] == [f"p{people.index(it['who'])}"]
    tuning = [e for e in ex.values() if e["gold"]["source"].startswith("chrono_bench/router_tuning.json")]
    assert tuning and {e["split"] for e in tuning} == {"train"}
    assert {e["language"] for e in ex.values()} == {"en", "ja"}


def test_a_content_question_is_never_labelled_with_a_kind_or_a_past():
    ex = build.build([], saltmere=False, concept_lab=False, seed=None, rulings=None)
    content = [e for e in ex.values() if e["key"] in ("route:kind", "route:past")
               and "content" in e["gold"]["accept"]]
    assert content == []


def test_saltmere_moment_checks_are_labelled_only_where_the_readers_checked(tmp_path):
    bank, qs = _bank(), _questions()
    first = next(q for q in qs.values() if q["order"] == "earliest"
                 and build.KIND_ALIASES.get(q["kind"], q["kind"]) == "act"
                 and all(isinstance(t, int) for t in q["answer_turns"]) and q["answer_turns"])
    planted = min(first["answer_turns"])
    turns = {t["turn"]: t for t in bank["turns"]}
    before, after = turns[planted - 1], turns[max(first["answer_turns"]) + 1]
    with_inference = next((t for t in bank["turns"] if t.get("inferences") and t["turn"] == planted), None)
    state = f"Wren ASKED YOU: {first['en']}"
    rows = {"hit": _moment("memory_moment", turns[planted]["content"], planted),
            "before": _moment("memory_moment", before["content"], before["turn"]),
            "after": _moment("memory_moment", after["content"], after["turn"])}
    if with_inference:
        rows["inference"] = _moment("memory_moment", with_inference["inferences"][0]["text"], planted)
    rec = {"model": "jev", "language": "en", "state": state, "questions": rows,
           "answers": {k: _yes(0.5) for k in rows}}
    other = {"type": "noul", "instructions": "Is the asker in the room?"}
    elsewhere = {"model": "jev", "language": "en", "frame": 4, "state": state, "questions": {"o": other},
                 "answers": {"o": {"type": "noul", "noul": 0.9}}}
    ex = build.build([str(_capture(tmp_path, [rec, elsewhere]))], gold_router=False, concept_lab=False, seed=None,
                      rulings=None)
    got = {k: ex[build.example_id(state, q)] for k, q in rows.items()}
    assert got["hit"]["gold"]["accept"] == ["yes"] and got["hit"]["task"] == "character_jev.memory_moment"
    assert got["before"]["gold"]["accept"] == ["no"]
    assert got["after"]["gold"] is None, "a later instance of a first time is still an instance"
    if with_inference:
        assert got["inference"]["gold"] is None
    unlabelled = ex[build.example_id(state, other)]
    assert unlabelled["gold"] is None
    assert {e["group"] for e in [*got.values(), unlabelled]} == {f"chrono_bench/questions.json#{first['id']}"}, \
        "every request about one bench question is one group, labelled or not"
    assert len({e["split"] for e in [*got.values(), unlabelled]}) == 1


def test_a_question_nothing_answers_is_no_for_every_row_it_checks(tmp_path):
    bank, qs = _bank(), _questions()
    never = next(q for q in qs.values() if not q["answer_turns"] and q["order"] in ("earliest", "latest")
                 and build.KIND_ALIASES.get(q["kind"], q["kind"]) in ("met", "act", "place"))
    row = bank["turns"][100]
    state = f"Wren ASKED YOU: {never['en']}"
    q = _moment("memory_moment", row["content"], row["turn"])
    rec = {"model": "jev", "language": "en", "state": state, "questions": {"m": q}, "answers": {"m": _yes(0.1)}}
    ex = build.build([str(_capture(tmp_path, [rec]))], gold_router=False, concept_lab=False, seed=None,
                      rulings=None)
    assert ex[build.example_id(state, q)]["gold"]["accept"] == ["no"]


def test_a_line_cut_off_mid_write_is_skipped(tmp_path):
    folder = tmp_path / "c" / "engine"
    folder.mkdir(parents=True)
    good = {"state": "S", "language": "en", "questions": {"a": {"type": "noul", "instructions": "Q?"}},
            "answers": {"a": {"type": "noul", "noul": 0.9}}}
    (folder / "2026-10-06.jsonl").write_text(json.dumps(good) + "\n" + '{"state": "S", "quest', encoding="utf-8")
    ex = build.build([str(tmp_path / "c")], gold_router=False, saltmere=False, concept_lab=False, seed=None,
                      rulings=None)
    assert len(ex) == 1


def test_the_file_is_written_whole_and_in_a_stable_order(tmp_path):
    ex = build.build([], saltmere=False, concept_lab=False, seed=None, rulings=None)
    out = build.write(ex, tmp_path / "examples.jsonl")
    lines = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == len(ex)
    assert lines == sorted(lines, key=lambda e: (e["split"], e["task"], e["id"]))
    assert not (tmp_path / "examples.jsonl.tmp").exists()


def test_a_seed_merges_by_its_count_and_keeps_its_sources(tmp_path):
    q = {"type": "choice", "instructions": "Is it raining in this scene?", "criteria": {"yes": "Yes.", "no": "No."}}
    seeded = {"state": "RAIN ON THE ROOF", "question": q, "key": "a", "language": "en", "group": "g",
              "gold": {"accept": ["yes"], "source": "bench#1"}, "sources": ["capture:old/2026-10-06.jsonl"],
              "steps": [], "models": ["jev"],
              "teacher": {"type": "choice", "probabilities": {"yes": 0.9, "no": 0.1}, "choice": "yes", "n": 3}}
    seed = tmp_path / "seed.jsonl"
    seed.write_text(json.dumps(seeded) + "\n", encoding="utf-8")
    rec = {"model": "jev", "language": "en", "state": "RAIN ON THE ROOF", "questions": {"a": q},
           "answers": {"a": _yes(0.5)}}
    ex = build.build([str(_capture(tmp_path, [rec]))], gold_router=False, saltmere=False, concept_lab=False,
                     seed=seed, rulings=None)
    [only] = ex.values()
    assert only["teacher"]["n"] == 4
    assert only["teacher"]["probabilities"]["yes"] == round((0.9 * 3 + 0.5) / 4, 4)
    assert only["gold"]["accept"] == ["yes"]
    assert set(only["sources"]) == {"capture:old/2026-10-06.jsonl", "capture:saltmere_on/2026-10-06.jsonl"}


def test_rulings_keep_relabel_or_drop_a_disputed_label(tmp_path):
    qs = [{"type": "choice", "instructions": f"Is this row {i} the moment?", "criteria": {"yes": "Yes.", "no": "No."}}
          for i in range(3)]
    seed = tmp_path / "seed.jsonl"
    seed.write_text("".join(json.dumps({"state": "S", "question": q, "key": f"m{i}", "language": "en", "group": "g",
                                        "gold": {"accept": ["no"], "source": f"bench#{i}"}}) + "\n"
                            for i, q in enumerate(qs)), encoding="utf-8")
    ids = [build.example_id("S", q) for q in qs]
    rulings = tmp_path / "rulings.json"
    rulings.write_text(json.dumps({"rulings": {
        ids[0]: {"ruling": "keep", "votes": {"no": 3}},
        ids[1]: {"ruling": "relabel", "accept": ["yes"], "votes": {"yes": 3}},
        ids[2]: {"ruling": "drop", "votes": {"yes": 2, "no": 1}}}}), encoding="utf-8")
    ex = build.build([], gold_router=False, saltmere=False, concept_lab=False, seed=seed, rulings=rulings)
    assert ex[ids[0]]["gold"]["accept"] == ["no"] and ex[ids[0]]["gold"]["ruled"] == {"no": 3}
    assert ex[ids[1]]["gold"]["accept"] == ["yes"] and ex[ids[1]]["gold"]["source"] == "bench#1"
    assert ex[ids[2]]["gold"] is None, "a label two judges of three dispute is no label at all"


def test_the_concept_lab_gives_present_mentioned_and_absent_people():
    ex = build.build([], gold_router=False, saltmere=False, seed=None, rulings=None)
    met = [e for e in ex.values() if e["task"] == "character_jev.memory_met"]
    bank = json.loads((ROOT / "tools" / "concept_lab" / "bank_large.json").read_text(encoding="utf-8"))
    present = sum(len([p for p in m["about"] if p.startswith("P_")]) for m in bank["memories"])
    mentioned = sum(len([p for p in m["concepts"] if p.startswith("P_") and p not in m["about"]])
                    for m in bank["memories"])
    assert sum(e["gold"]["accept"] == ["yes"] for e in met) == present
    assert sum(e["gold"]["accept"] == ["no"] for e in met) == mentioned + len(bank["memories"])
    groups = defaultdict(set)
    for e in met:
        groups[e["group"]].add(e["split"])
    assert all(len(sides) == 1 for sides in groups.values()), "one memory's people go to one side"


def test_the_committed_seed_and_rulings_agree_with_each_other():
    """The seed holds only what a bench paid for -- a gold label and the
    teacher's answer -- every accepted option is one the question offers, and
    every ruling names an example a build still produces (a ruling on wording
    that has since changed would silently stop applying)."""
    seed = list(build.read_examples(build.SEED))
    assert seed and all(e["gold"] and e["teacher"] for e in seed)
    for e in seed:
        assert set(e["gold"]["accept"]) <= set(e["question"]["criteria"]), e["id"]
        assert any(str(s).startswith("capture:") for s in e["sources"])
    ex = build.build([])
    rulings = json.loads(build.RULINGS.read_text(encoding="utf-8"))["rulings"]
    assert set(rulings) <= set(ex), "a ruling whose example no build produces"
    for eid, ruling in rulings.items():
        if ruling["ruling"] == "drop":
            assert ex[eid]["gold"] is None
        else:
            assert ex[eid]["gold"]["ruled"] == ruling["votes"]
            assert set(ex[eid]["gold"]["accept"]) <= set(ex[eid]["question"]["criteria"])
