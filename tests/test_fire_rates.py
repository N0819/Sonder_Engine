"""The fire-rate harness, and specifically its denominators.

`tools/fire_rates.py` exists because four mechanisms in this engine were built,
documented, tested and never ran once, and none of them looked dead from
reading the code. The harness is only worth having if its numbers are honest,
and the one way it can lie is the denominator:

    memory_disputes, measured against every memory row      0 of 6,460
    memory_disputes, measured against beats that had one    0 of 178

The first number is noise -- the field did not exist for most of that corpus.
The second sits beside a sibling introduced in the same commit, on the same 178
results, firing 78% of the time, and that pair is a diagnosis. So the rule the
harness encodes and these tests pin: **a result that never carried the field
was never a chance to use it.**

The harness reads sqlite directly and imports no engine module, so it is safe
against a live database and testable against a hand-built one.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fire_rates  # noqa: E402


SCHEMA = """
CREATE TABLE turns (id INTEGER PRIMARY KEY, chat_id INT, idx INT,
                    player_input TEXT, created TEXT, frame_id TEXT);
CREATE TABLE steps (id INTEGER PRIMARY KEY, turn_id INT, key TEXT, label TEXT,
                    ord INT, stale INT DEFAULT 0);
CREATE TABLE variants (id INTEGER PRIMARY KEY, step_id INT, content TEXT,
                       created TEXT, active INT DEFAULT 1, reasoning TEXT);
CREATE TABLE memories (id INTEGER PRIMARY KEY, chat_id INT, char_id INT,
                       turn_id INT, salience REAL, importance REAL,
                       disputed TEXT DEFAULT '', encoding_valence REAL DEFAULT 0.0,
                       archived INT DEFAULT 0, kind TEXT, event_key TEXT);
CREATE TABLE chat_chars (chat_id INT, char_id INT, status TEXT, state TEXT,
                         sheet TEXT);
"""


def _db(tmp_path, turns=(), results_by_turn=None, memories=(), states=()):
    """A corpus small enough to reason about by hand."""
    path = tmp_path / "corpus.db"
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    for tid, chat_id, idx in turns:
        con.execute("INSERT INTO turns (id, chat_id, idx) VALUES (?,?,?)",
                    (tid, chat_id, idx))
    step_id = 0
    for tid, results in (results_by_turn or {}).items():
        step_id += 1
        con.execute("INSERT INTO steps (id, turn_id, key) VALUES (?,?,?)",
                    (step_id, tid, "interaction_loop"))
        con.execute(
            "INSERT INTO variants (step_id, content, active) VALUES (?,?,1)",
            (step_id, json.dumps({"character_results": results})))
    for row in memories:
        con.execute(
            "INSERT INTO memories (chat_id, char_id, turn_id, salience, "
            "importance, disputed, encoding_valence, archived, kind, event_key)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)", row)
    for chat_id, char_id, state in states:
        con.execute("INSERT INTO chat_chars (chat_id, char_id, status, state, "
                    "sheet) VALUES (?,?,'active',?,'')", (chat_id, char_id,
                                                          json.dumps(state)))
    con.commit()
    con.close()
    return path


def _by_name(report):
    return {m["name"]: m for m in report["mechanisms"]}


def _collect(path, **kw):
    con = fire_rates.connect(str(path))
    try:
        return fire_rates.collect(con, **kw)
    finally:
        con.close()


class TestTheDenominatorIsTheChance:
    """The whole reason this file exists."""

    def test_older_results_do_not_dilute_a_new_field(self, tmp_path):
        """Three beats predate the field, two carry it and neither used it.
        The honest reading is 0 of 2, not 0 of 5."""
        path = _db(tmp_path,
                   turns=[(1, 7, 0)],
                   results_by_turn={1: [
                       {"appraisal": {}},
                       {"appraisal": {}},
                       {"appraisal": {}},
                       {"appraisal": {}, "memory_disputes": []},
                       {"appraisal": {}, "memory_disputes": []},
                   ]})
        row = _by_name(_collect(path))["memory_disputes"]
        assert (row["fired"], row["chances"]) == (0, 2)

    def test_a_used_field_counts_as_fired(self, tmp_path):
        path = _db(tmp_path,
                   turns=[(1, 7, 0)],
                   results_by_turn={1: [
                       {"appraisal": {}, "memory_disputes": []},
                       {"appraisal": {}, "memory_disputes": [
                           {"memory_ref": "event:abc", "now_reads": "a lie"}]},
                   ]})
        row = _by_name(_collect(path))["memory_disputes"]
        assert (row["fired"], row["chances"]) == (1, 2)

    def test_no_chances_is_not_zero_percent(self, tmp_path):
        """A mechanism nothing could have used reports an absence of evidence,
        never a rate. `0%` and `never had the option` are different claims and
        the harness must not collapse them."""
        path = _db(tmp_path, turns=[(1, 7, 0)],
                   results_by_turn={1: [{"appraisal": {}}]})
        report = _collect(path)
        row = _by_name(report)["memory_disputes"]
        assert row["chances"] == 0 and row["rate"] is None
        assert "no chances" in fire_rates.render(report)

    def test_an_empty_list_is_a_chance_declined(self, tmp_path):
        """Present-and-empty is the interesting case: the model was asked and
        said nothing. That has to count in the denominator or the rate reads
        100% forever."""
        path = _db(tmp_path, turns=[(1, 7, 0)],
                   results_by_turn={1: [{"appraisal": {},
                                         "remember_lines": []}]})
        row = _by_name(_collect(path))["remember_lines"]
        assert (row["fired"], row["chances"]) == (0, 1)


class TestTheMemoryBank:
    def test_importance_counts_as_revised_only_when_it_moved(self, tmp_path):
        """`effective_importance` falls back to salience, so a row whose
        importance merely MIRRORS its salience has never been revised -- and
        that is the majority of every bank."""
        path = _db(tmp_path, turns=[(1, 7, 0)], memories=[
            (7, 1, 1, 0.60, None, "", 0.0, 0, "episode", "event:a"),
            (7, 1, 1, 0.60, 0.60, "", 0.0, 0, "episode", "event:b"),
            (7, 1, 1, 0.60, 0.72, "", 0.0, 0, "episode", "event:c"),
        ])
        row = _by_name(_collect(path))["importance revised"]
        assert (row["fired"], row["chances"]) == (1, 3)

    def test_a_not_null_default_is_measured_as_non_neutral(self, tmp_path):
        """`encoding_valence` is NOT NULL DEFAULT 0.0. Testing for null reports
        100% and means nothing. Only banks that ever record a non-zero one are
        counted as having had the column live at all."""
        path = _db(tmp_path, turns=[(1, 7, 0)], memories=[
            (7, 1, 1, 0.6, None, "", 0.0, 0, "episode", "event:a"),
            (7, 1, 1, 0.6, None, "", -0.4, 0, "episode", "event:b"),
            (8, 1, 1, 0.6, None, "", 0.0, 0, "episode", "event:c"),
        ])
        row = _by_name(_collect(path))["encoding_valence non-neutral"]
        # chat 8 never records one, so its row is not a declined chance --
        # it is a bank where the mechanism was never live.
        assert (row["fired"], row["chances"]) == (1, 2)

    def test_a_dispute_is_any_non_empty_blob(self, tmp_path):
        path = _db(tmp_path, turns=[(1, 7, 0)], memories=[
            (7, 1, 1, 0.6, None, "", 0.0, 0, "episode", "event:a"),
            (7, 1, 1, 0.6, None, '{"reading":"he was lying"}', 0.0, 0,
             "episode", "event:b"),
        ])
        row = _by_name(_collect(path))["disputed"]
        assert (row["fired"], row["chances"]) == (1, 2)


class TestScope:
    def test_last_n_is_per_chat_not_global(self, tmp_path):
        """One long story and several short ones: a global tail would report
        `the last 3 turns` as three turns of a single chat and silently drop
        every other story from the corpus."""
        turns = [(i + 1, 1, i) for i in range(10)] + \
                [(101, 2, 0), (102, 2, 1), (103, 2, 2), (104, 2, 3)]
        path = _db(tmp_path, turns=turns)
        assert _collect(path, last=3)["scope"]["turns"] == 6
        assert _collect(path, last=3)["scope"]["chats"] == 2

    def test_one_chat_can_be_isolated(self, tmp_path):
        path = _db(tmp_path, turns=[(1, 1, 0), (2, 2, 0), (3, 2, 1)])
        assert _collect(path, chat=2)["scope"]["turns"] == 2

    def test_an_empty_corpus_does_not_divide_by_zero(self, tmp_path):
        path = _db(tmp_path)
        report = _collect(path)
        assert all(m["rate"] is None for m in report["mechanisms"])
        assert fire_rates.render(report)  # renders rather than raising


class TestCapacity:
    def test_it_reports_the_floor_as_well_as_the_ceiling(self, tmp_path):
        """A cap means nothing until the tier is reachable. Measured over the
        live corpus this read `0 of 14 have ever held a project` -- which is
        why `projects at cap` reading 0% was not the reassurance it looked
        like."""
        path = _db(tmp_path, turns=[(1, 1, 0)], states=[
            (1, 1, {"active_state": {"wants": [{}, {}, {}]},
                    "interior": {"intentions": [{"status": "active"}],
                                 "projects": [], "former_projects": []}}),
            (1, 2, {"active_state": {"wants": [{}]},
                    "interior": {"intentions": [],
                                 "projects": [{"status": "active"}],
                                 "former_projects": []}}),
        ])
        rows = _by_name(_collect(path))
        assert rows["wants at cap (3)"]["fired"] == 1
        assert rows["has ever held a project"]["fired"] == 1
        assert rows["has ever held a project"]["chances"] == 2

    def test_an_ended_project_still_proves_the_path_ran(self, tmp_path):
        path = _db(tmp_path, turns=[(1, 1, 0)], states=[
            (1, 1, {"interior": {"projects": [],
                                 "former_projects": [{"id": "p1"}]}}),
        ])
        assert _by_name(_collect(path))["has ever held a project"]["fired"] == 1


class TestSalienceShape:
    def test_it_reports_a_distribution_rather_than_a_rate(self, tmp_path):
        """`effective_importance` fires on every row, always -- so a fire rate
        would read 100% and tell you nothing. A term that always fires at the
        same value is doing no work, and only the spread shows it."""
        path = _db(tmp_path, turns=[(1, 7, 0)], memories=[
            (7, 1, 1, 0.65, None, "", 0.0, 0, "episode", "event:%d" % i)
            for i in range(20)
        ])
        sal = _collect(path)["salience"]
        assert sal["n"] == 20
        assert sal["spread_p10_p90"] == 0.0
        assert sal["modal_band_share"] == 1.0

    def test_the_fallback_matches_effective_importance(self, tmp_path):
        """Revised importance where there is one, minted salience otherwise --
        the same rule `memory.effective_importance` applies, or the histogram
        describes a column ranking never reads."""
        path = _db(tmp_path, turns=[(1, 7, 0)], memories=[
            (7, 1, 1, 0.20, 0.90, "", 0.0, 0, "episode", "event:a"),
        ])
        sal = _collect(path)["salience"]
        assert sal["histogram"]["0.9-1.0"] == 1
        assert sal["histogram"]["0.2-0.3"] == 0


def test_it_never_opens_the_database_for_writing(tmp_path):
    """Safe to run against a live engine.db while the server is up, which is
    the only way anyone will actually run it."""
    path = _db(tmp_path, turns=[(1, 7, 0)])
    con = fire_rates.connect(str(path))
    try:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("DELETE FROM turns")
    finally:
        con.close()
