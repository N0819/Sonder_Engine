"""The perception quality harness, and specifically its two directions.

tools/perception_quality.py exists so the deterministic-composer branch's
acceptance bar — same quality, just faster — is falsifiable. The one way the
harness can lie is by conflating its two directions: information present
that was NOT entitled (a leak, the serious direction) versus entitled
information missing (an under-grant). These tests pin each direction with a
planted defect and a clean control, entirely on synthetic data — no
database, no engine.db, fast-tier safe.

The harness reuses the engine's own checkers, resolved by name; where a
symbol is missing on a given tree the affected test skips rather than
passing vacuously.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Appended, never inserted at 0: tools/ contains modules (pipeline_trace)
# that shadow same-named top-level modules if tools/ precedes the repo root
# on sys.path, which breaks later-collected tests in the same pytest run.
_TOOLS_DIR = str(Path(__file__).resolve().parents[1] / "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.append(_TOOLS_DIR)

import perception_judge
import perception_latency
import perception_quality
import perception_retrieval

ENGINE, MISSING = perception_quality.resolve_engine()


def _needs(*names):
    absent = [n for n in names if not ENGINE.get(n)]
    if absent:
        pytest.skip(f"engine symbols unavailable on this tree: {absent}")


def _entitlement(**overrides):
    base = {
        "observer": "Maren Voss",
        "stage": "perception_outcome",
        "is_player": False,
        "ledger_present": True,
        "allowed_forms": ["Maren Voss", "Teodor Hale"],
        "unknown_sources": [
            {"name": "Ondine Pell",
             "appearance": "a wiry woman in a patched grey coat",
             "aliases": []}],
        "unknown_sources_post": [
            {"name": "Ondine Pell",
             "appearance": "a wiry woman in a patched grey coat",
             "aliases": []}],
        "roster_names": ["Maren Voss", "Teodor Hale", "Ondine Pell"],
        "entitled_lines": [],
        "unentitled_lines": [],
        "concealed_lines": [],
        "ungated_lines": 0,
        "same_room_lines": [],
        "gate_available": True,
        "spoken_bodies": [],
        "declared_player_lines": [],
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# Metric A — leaks
# --------------------------------------------------------------------------

def test_unearned_identity_is_a_leak_and_a_label_is_not():
    _needs("_scrub_unknown_identities")
    ent = _entitlement()
    leaked = perception_quality.score_view(
        "Ondine Pell crosses to the shelf and lifts the lantern.",
        ent, ENGINE)
    assert leaked["identity_leaks"] == ["Ondine Pell"]
    # the same fact through the entitled label is clean
    clean = perception_quality.score_view(
        "The wiry woman in a patched grey coat crosses to the shelf.",
        ent, ENGINE)
    assert clean["identity_leaks"] == []


def test_identity_metric_declines_without_a_ledger():
    _needs("_scrub_unknown_identities")
    ent = _entitlement(ledger_present=False)
    findings = perception_quality.score_view(
        "Ondine Pell crosses to the shelf.", ent, ENGINE)
    assert findings["identity_leaks"] == []
    assert "identity_no_ledger" in findings["checks_skipped"]


def test_unentitled_line_present_is_a_leak():
    _needs("_contains_quote", "_quote_body")
    quote = "There is a second key under the floorboard."
    ent = _entitlement(unentitled_lines=[
        {"speaker": "Teodor Hale", "quote": quote, "volume": "mutter"}])
    hit = perception_quality.score_view(
        f'You hear Teodor Hale say, "{quote}"', ent, ENGINE)
    assert len(hit["unentitled_line_leaks"]) == 1
    miss = perception_quality.score_view(
        "Teodor Hale mutters something you cannot make out.", ent, ENGINE)
    assert miss["unentitled_line_leaks"] == []


def test_invented_quote_is_flagged_and_spoken_quote_is_not():
    _needs("_scrub_invented_dialogue")
    spoken = "We leave before the tide turns, all of us."
    ent = _entitlement(spoken_bodies=[spoken])
    invented = perception_quality.score_view(
        'Teodor Hale says, "You promised me the ledger years ago."',
        ent, ENGINE)
    assert invented["invented_quotes"]
    legitimate = perception_quality.score_view(
        f'Teodor Hale says, "{spoken}"', ent, ENGINE)
    assert legitimate["invented_quotes"] == []


def test_self_narration_is_counted():
    _needs("_strip_self_narration")
    ent = _entitlement()
    findings = perception_quality.score_view(
        "Maren stands and crosses to the window. "
        "The lantern gutters on the stair.", ent, ENGINE)
    assert findings["self_narration"] >= 1


def test_undeclared_player_speech_only_checks_player_views():
    _needs("_scrub_undeclared_player_speech")
    fabricated = 'You say, "I never touched the ledger, I swear it."'
    npc_ent = _entitlement(is_player=False)
    assert perception_quality.score_view(
        fabricated, npc_ent, ENGINE)["undeclared_player_speech"] == []
    player_ent = _entitlement(is_player=True, declared_player_lines=[])
    assert perception_quality.score_view(
        fabricated, player_ent, ENGINE)["undeclared_player_speech"]


# --------------------------------------------------------------------------
# Metric A — under-grants
# --------------------------------------------------------------------------

def test_missing_entitled_line_is_an_under_grant():
    _needs("_contains_quote")
    quote = "The ferry does not run on festival days."
    line = {"speaker": "Teodor Hale", "quote": quote, "volume": "normal",
            "same_room": True, "same_room_pre": True}
    ent = _entitlement(entitled_lines=[line],
                       same_room_lines=[{"speaker": "Teodor Hale",
                                         "quote": quote,
                                         "volume": "normal"}])
    missing = perception_quality.score_view(
        "Teodor Hale stands by the window, saying nothing you retain.",
        ent, ENGINE)
    assert len(missing["entitled_lines_missing"]) == 1
    assert len(missing["entitled_lines_missing_high_confidence"]) == 1
    assert missing["same_room_lines_missing"] == 1
    delivered = perception_quality.score_view(
        f'Teodor Hale says, "{quote}"', ent, ENGINE)
    assert delivered["entitled_lines_missing"] == []
    assert delivered["same_room_lines_missing"] == 0


def test_residue_views_owe_no_lines_but_still_cannot_leak():
    _needs("_contains_quote", "_scrub_unknown_identities")
    quote = "Nobody has touched the ledger since spring."
    ent = _entitlement(entitled_lines=[
        {"speaker": "Teodor Hale", "quote": quote, "volume": "loud",
         "same_room": True, "same_room_pre": True}])
    findings = perception_quality.score_view(
        "Darkness. A sound, huge and wordless, reaches down and is gone.",
        ent, ENGINE)
    assert findings["residue"] is True
    assert findings["entitled_lines_missing"] == []


# --------------------------------------------------------------------------
# Entitlement construction details
# --------------------------------------------------------------------------

def test_spoken_body_walk_collects_every_source_shape():
    steps = [
        {"sequence": [{"type": "speech", "text": "From the sequence."}]},
        {"dialogue_log": [{"speaker": "A", "exact_quote": "From the log."}]},
        {"character_results": {"7": {"speech": "From a character result."}}},
    ]
    bodies = perception_quality.collect_spoken_bodies(steps)
    assert "From the sequence." in bodies
    assert "From the log." in bodies
    assert "From a character result." in bodies


def test_position_overlay_moves_only_the_moved():
    scene = {"positions": {"Maren Voss": "cellar", "Teodor Hale": "taproom"}}
    out = perception_quality._overlay_positions(
        scene, {"positions": {"Teodor Hale": "cellar"}})
    assert out["positions"]["Teodor Hale"] == "cellar"
    assert out["positions"]["Maren Voss"] == "cellar"
    assert scene["positions"]["Teodor Hale"] == "taproom"  # input untouched


def test_concealed_line_with_empty_list_is_concealed_from_everyone():
    entry = {"visibility": "concealed", "conceal_from": []}
    assert perception_quality._concealed_from(entry, "Maren Voss")
    entry = {"visibility": "concealed", "conceal_from": ["Teodor Hale"]}
    assert not perception_quality._concealed_from(entry, "Maren Voss")
    assert perception_quality._concealed_from(entry, "Teodor Hale")


# --------------------------------------------------------------------------
# Metric B — lexical proxy behavior
# --------------------------------------------------------------------------

def test_trigram_cosine_orders_twin_over_stranger():
    twin = perception_retrieval.trigram_cosine(
        "The lantern gutters on the stair.",
        "The lantern gutters on the stair.")
    related = perception_retrieval.trigram_cosine(
        "The lantern gutters on the stair.",
        "The lantern gutters on the cellar stair.")
    stranger = perception_retrieval.trigram_cosine(
        "The lantern gutters on the stair.",
        "Eleven crates wait on the ferry dock.")
    assert twin == pytest.approx(1.0)
    assert twin > related > stranger


def test_pessimistic_rank_counts_ties_against_the_target():
    # a verbatim twin scores identically -> rank 2, not rank 1: duplicate
    # banks must SHOW their retrieval damage, not hide it in tie-breaks
    assert perception_retrieval.pessimistic_rank([1.0, 1.0, 0.2], 0) == 2
    assert perception_retrieval.pessimistic_rank([1.0, 0.4, 0.2], 0) == 1


def test_embedding_hook_refuses_offline():
    with pytest.raises(RuntimeError):
        perception_retrieval.embed_texts_hook(["anything"])


# --------------------------------------------------------------------------
# Metric C — judge scaffold
# --------------------------------------------------------------------------

def _perfect_judge(prompt):
    """A stand-in judge that reads the fact sheet out of its own prompt and
    answers by exact string checks — the mechanically correct verdict."""
    import json as _json
    import re as _re
    sheet_text = prompt.split("FACT SHEET (ground truth):\n", 1)[1] \
        .split("\n\nVIEW UNDER AUDIT:\n", 1)[0]
    view = prompt.split("\n\nVIEW UNDER AUDIT:\n", 1)[1] \
        .split("\n\nReturn STRICT JSON", 1)[0]
    sheet = _json.loads(sheet_text)
    leaks = [l["quote"] for l in sheet["not_entitled_lines"]
             if l["quote"] in view]
    leaks += [n for n in sheet["unrecognized_identities"]
              if _re.search(rf"\b{_re.escape(n)}\b", view)]
    omissions = [l["quote"] for l in sheet["entitled_lines"]
                 if l["quote"] not in view]
    return _json.dumps({"leaks": leaks, "omissions": omissions,
                        "contradictions": [], "reads_as_perception": True,
                        "clean": not (leaks or omissions)})


def test_calibration_passes_a_correct_judge_and_gates_a_lazy_one():
    judge = perception_judge.CalibratedJudge(_perfect_judge)
    report = judge.calibrate()
    assert report["fpr"] == 0.0
    assert report["fnr"] == 0.0
    assert judge.trusted

    lazy = perception_judge.CalibratedJudge(
        lambda prompt: '{"leaks": [], "omissions": [], "contradictions": [],'
                       ' "reads_as_perception": true, "clean": true}')
    lazy.calibrate()
    assert not lazy.trusted  # passes every defect -> FNR 1.0
    with pytest.raises(RuntimeError):
        lazy.verdict({"observer": "x"}, "view")


def test_uncalibrated_judge_refuses_verdicts():
    judge = perception_judge.CalibratedJudge(_perfect_judge)
    with pytest.raises(RuntimeError):
        judge.verdict({"observer": "x"}, "view")


def test_unparseable_verdict_is_a_non_verdict():
    assert perception_judge.parse_verdict("I think it looks fine!") is None
    assert perception_judge.parse_verdict("") is None


def test_fact_sheet_carries_no_prose_but_the_typed_facts():
    ent = _entitlement(
        entitled_lines=[{"speaker": "Teodor Hale", "quote": "A line.",
                         "volume": "normal", "same_room": True,
                         "same_room_pre": True}])
    sheet = perception_judge.fact_sheet(ent)
    assert sheet["observer"] == "Maren Voss"
    assert sheet["unrecognized_identities"] == ["Ondine Pell"]
    assert sheet["entitled_lines"] == [
        {"speaker": "Teodor Hale", "quote": "A line."}]


# --------------------------------------------------------------------------
# Metric D — timing arithmetic on synthetic rows
# --------------------------------------------------------------------------

def test_residue_views_do_not_count_as_model_calls():
    assert perception_latency._is_residue_view("Darkness. Nothing reaches you.")
    assert not perception_latency._is_residue_view("You are in the taproom.")


def test_stage_durations_on_a_synthetic_database(tmp_path):
    import sqlite3
    db = tmp_path / "toy.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE turns (id INTEGER PRIMARY KEY, chat_id INT, idx INT,
                            created REAL);
        CREATE TABLE steps (id INTEGER PRIMARY KEY, turn_id INT, key TEXT,
                            label TEXT, ord INT, stale INT DEFAULT 0);
        CREATE TABLE variants (id INTEGER PRIMARY KEY, step_id INT,
                               content TEXT, created REAL, active INT);
    """)
    con.execute("INSERT INTO turns VALUES (1, 1, 0, 100.0)")
    steps = [(1, 1, "director_interpret", "", 0),
             (2, 1, "perception_act", "", 1),
             (3, 1, "director_resolve", "", 2),
             (4, 1, "perception_outcome", "", 3)]
    con.executemany("INSERT INTO steps VALUES (?,?,?,?,?,0)", steps)
    variants = [(1, 1, "{}", 110.0, 1),   # interpret: 10s
                (2, 2, "{}", 130.0, 1),   # act: 20s
                (3, 3, "{}", 140.0, 1),   # resolve: 10s
                (4, 4, "{}", 180.0, 1)]   # outcome: 40s
    con.executemany("INSERT INTO variants VALUES (?,?,?,?,?)", variants)
    con.commit()
    con.close()
    out = perception_latency.stage_durations(
        sqlite3.connect(f"file:{db}?mode=ro", uri=True))
    assert out["turns_usable_for_timing"] == 1
    # perception 60s of 80s total
    assert out["perception_share_of_wallclock_pct"] == 75.0
