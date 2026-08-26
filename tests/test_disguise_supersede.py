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

from persist.commit import _supersede_disguises


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
    # The whole singular GROUP, not just this kind: a body cannot be
    # disguised and transformed at once, and scoping to one kind let it.
    assert args == (72, "physical_disguise", "physical_transformation",
                    "glamour_2", "Hinami")


def test_an_ending_ends_every_row_on_that_body():
    """THE ONE THAT MAKES 'my glamour comes undone' work. No condition_id
    exclusion: all of them go, including ids the Director never saw."""
    cur = _Cursor()
    _supersede_disguises(cur, 72, _disguise(active=0), "glamour_2")
    sql, args = cur.calls[0]
    assert "SET active=0" in sql
    assert "condition_id<>?" not in sql
    assert args == (72, "physical_disguise", "physical_transformation",
                    "Hinami")


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

    # commit_entities.py since the split carved the entity domain out of
    # commit.py; the pinned block is commit_world_entities' condition loop.
    src = (Path(__file__).resolve().parents[1]
           / "persist" / "commit_entities.py").read_text(encoding="utf-8")
    block = src[src.index("for cond_id, cond_list in"):]
    # Bounded by the FUNCTION's own end, not by a character count. The
    # window used to stop at 4000 characters, which is not a boundary of
    # anything: adding provenance comments inside the loop moved the call
    # past it and failed a test about whether the call exists. A syntactic
    # end cannot drift with the prose around it.
    block = block[:block.index('\n    return {"entities_committed"')]
    assert "_supersede_disguises(c, cid, cond, cid_val)" in block


def test_the_reader_side_picks_the_newest_rather_than_whichever(temp_db):
    """Belt and braces for rows that predate the rule: with several already
    active, the read must be deterministic and must prefer the most recent
    declaration -- what the reader just watched happen."""
    from story.scene import active_disguises

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


def _insert(temp_db, chat_id, cid, started, presented, known_to, active=1):
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,payload,active) VALUES(?,?,?,?,?,?,?)",
        (cid, chat_id, "Hinami", "physical_disguise", started,
         json.dumps({"condition_id": cid, "subject_id": "Hinami",
                     "kind": "physical_disguise",
                     "state": {"presented_appearance": presented,
                               "known_to": known_to}}), active))


def test_knowing_the_truth_survives_a_row_losing(temp_db):
    """KNOWLEDGE ACCUMULATES; APPEARANCE DOES NOT.

    Reproduces chat 74 exactly. A branch copies conditions wholesale without
    a write, so the supersede rule never runs on them -- chat 72 carried two
    rows started at the SAME clock second and its descendants inherited both.
    Equal `started_at` turns the reader's ORDER BY into a coin flip resolved
    by rowid, and the row that won carried an empty `known_to` while the
    other named The Doctor. He had been told, and was the only one fooled.
    """
    from story.scene import active_disguises

    chat_id = temp_db.qi("INSERT INTO chats(name,created) VALUES('t',0.0)")
    _insert(temp_db, chat_id, "told", 1057.0, "an older form", ["The Doctor"])
    _insert(temp_db, chat_id, "silent", 1057.0, "the newest form", [])

    live = active_disguises(chat_id)["hinami"]
    assert live["presented_appearance"] == "the newest form", \
        "the newest row still decides the one outward form"
    assert live["known_to"] == ["The Doctor"], \
        "a superseded row does not un-tell the person it told"


def test_an_inactive_row_contributes_nothing(temp_db):
    """Accumulating from ENDED rows would make a disguise unusable against
    anyone who ever saw through an earlier one."""
    from story.scene import active_disguises

    chat_id = temp_db.qi("INSERT INTO chats(name,created) VALUES('t',0.0)")
    _insert(temp_db, chat_id, "old", 100.0, "gone", ["Marta"], active=0)
    _insert(temp_db, chat_id, "now", 200.0, "current", ["The Doctor"])

    assert active_disguises(chat_id)["hinami"]["known_to"] == ["The Doctor"]
