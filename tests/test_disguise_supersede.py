"""One active disguise per body, and an ending that actually ends it.

The same rule now covers `physical_transformation` -- both are singular by
nature, a body presenting one outward form and being one thing -- so the kind
is a bound parameter rather than a literal. See
`tests/test_physical_transformation.py` for the transformation half.

A body presents one outward form. Nothing made that true: the Director minted
a fresh `condition_id` per reroll rather than reusing one, and chat 72 ended up
with THREE active `physical_disguise` rows on the same subject, each carrying
different `presented_appearance` prose. `active_disguises` keys by subject, so
one of them silently decided what every observer saw -- and since the scan had
no ORDER BY, which one could change between turns. Live symptom: the glamour
worked, then stopped, then half-worked.

The half that matters for play is the ENDING. "You allow your glamour to come
undone" is a statement about the body, not about a row. The Director cannot
name ids it has never been shown, so ending only the id it happens to write
would leave the other rows standing and the glamour would survive its own
undoing -- with the newest-wins rule, ending the newest simply promotes the
next one down.
"""

import json

import pytest

from commit import _supersede_disguises


class _Cursor:
    """Enough of a DB cursor to record what the rule tried to do."""

    def __init__(self):
        self.calls = []

    def execute(self, sql, args=()):
        self.calls.append((" ".join(sql.split()), args))


def _disguise(subject="Hinami", active=1, kind="physical_disguise"):
    return {"subject_id": subject, "kind": kind, "active": active,
            "state": {"presented_appearance": "an ordinary traveller"}}


def test_a_new_disguise_supersedes_every_other_one_on_that_body():
    cur = _Cursor()
    _supersede_disguises(cur, 72, _disguise(), "glamour_2")
    sql, args = cur.calls[0]
    assert "SET active=0" in sql
    assert "condition_id<>?" in sql, "the row just written must survive"
    assert args == (72, "physical_disguise", "glamour_2", "Hinami")


def test_an_ending_ends_every_row_on_that_body():
    """THE ONE THAT MAKES 'my glamour comes undone' work. No condition_id
    exclusion: all of them go, including ids the Director never saw."""
    cur = _Cursor()
    _supersede_disguises(cur, 72, _disguise(active=0), "glamour_2")
    sql, args = cur.calls[0]
    assert "SET active=0" in sql
    assert "condition_id<>?" not in sql
    assert args == (72, "physical_disguise", "Hinami")


def test_it_is_scoped_to_the_one_body():
    for active in (0, 1):
        cur = _Cursor()
        _supersede_disguises(cur, 72, _disguise(active=active), "x")
        sql, _args = cur.calls[0]
        assert "lower(subject_id)=lower(?)" in sql
        assert "chat_id=?" in sql


def test_subject_matching_is_case_insensitive():
    """`subject_id` is a model-written name, so "hinami" and "Hinami" are the
    same body and a case difference must not orphan a row."""
    cur = _Cursor()
    _supersede_disguises(cur, 72, _disguise(subject="hinami"), "x")
    assert "lower(subject_id)=lower(?)" in cur.calls[0][0]


@pytest.mark.parametrize("kind", ["awareness", "wound", ""])
def test_no_other_condition_kind_is_touched(kind):
    """Awareness, wounds and the rest are legitimately many-per-body. Only a
    disguise is singular."""
    cur = _Cursor()
    _supersede_disguises(cur, 72, _disguise(kind=kind), "x")
    assert cur.calls == []


def test_a_subjectless_condition_is_left_alone():
    """Matching on an empty subject would deactivate every disguise in the
    chat, which is the loudest possible way to get this wrong."""
    cur = _Cursor()
    _supersede_disguises(cur, 72, _disguise(subject="  "), "x")
    assert cur.calls == []


def test_the_rule_runs_on_the_live_commit_path():
    """Pinned on source: a helper nothing calls is a rule that does not
    exist, and this one is invisible until a second disguise appears."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "commit.py").read_text(encoding="utf-8")
    block = src[src.index("for cond_id, cond_list in"):]
    block = block[:block.index("\n    for ", 200)] if "\n    for " in block[200:] \
        else block[:4000]
    assert "_supersede_disguises(c, cid, cond, cid_val)" in block


def test_the_reader_side_picks_the_newest_rather_than_whichever(temp_db):
    """Belt and braces for rows that predate the rule: with several already
    active, the read must be deterministic and must prefer the most recent
    declaration -- what the reader just watched happen."""
    from scene import active_disguises

    # world_conditions.chat_id is a real foreign key.
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,created) VALUES('t',0.0)")

    for n, (started, presented) in enumerate([
        (100.0, "an older disguise"),
        (200.0, "the newest disguise"),
    ]):
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,"
            "kind,started_at,payload,active) VALUES(?,?,?,?,?,?,1)",
            (f"d{n}", chat_id, "Hinami", "physical_disguise", started,
             json.dumps({"subject_id": "Hinami",
                         "state": {"presented_appearance": presented}})))

    assert active_disguises(chat_id)["hinami"]["presented_appearance"] == \
        "the newest disguise"
