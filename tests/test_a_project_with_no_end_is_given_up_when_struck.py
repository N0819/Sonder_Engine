"""A project with no stated end, struck, is given up -- never left held.

When a mind strikes a project in its notebook the read-back asks HOW it ended
(`strike_kind`: "It is finished: what would end it has come", or set aside),
and the compile sends `satisfy` for "done", `displace` otherwise. A project
with no `satisfied_when` (authored ones routinely have none) cannot be
satisfied at all -- `apply_project_ops` refuses it, by design, because such a
project re-arms at every occasion -- so a "done" read back for one was refused
with a warning nobody read, and the mind found the project held again next
beat, its strike gone (review 2026-11-01, mind_affect_psychology F17,
reproduced: pa1 still live after `satisfy` with the reason "the winter is over
and the light never failed").

A project the mind was shown with nothing that would finish it has nothing
"done" can mean, so that question is not asked of it: the strike, with its
stated reason, gives it up (`displace`), and the floor on `satisfy` stays.
"""

from __future__ import annotations

from mind import affect, character_jev as jev

WHY = "the winter is over and the light never failed"


def _holding(row):
    return jev.Holding(name="Ilse", notebook={"what_you_are_about": [row]})


def _strike(pid):
    return {"notebook": [{"id": pid, "strike": WHY}]}


def test_how_it_ended_is_not_asked_of_a_project_with_no_end():
    h = _holding({"id": "pa1", "note": "Keep the lighthouse lit"})
    assert "nb:0:strike" not in jev.after_questions(h, _strike("pa1"))


def test_how_it_ended_is_still_asked_where_an_end_was_named():
    h = _holding({"id": "p3", "note": "Chart the shoals",
                  "until": "the harbour master posts the new chart"})
    assert "nb:0:strike" in jev.after_questions(h, _strike("p3"))


def test_the_unasked_strike_gives_the_project_up_with_its_reason():
    """What the compile sends when the kind is unasked (`pick` -> None):
    displace, which `apply_project_ops` honours."""
    done = jev.pick({}, "nb:0:strike") == "done"
    op = {"op": "satisfy" if done else "displace", "id": "pa1", "why": WHY}
    live, former, _w = affect.apply_project_ops(
        [{"id": "pa1", "project": "Keep the lighthouse lit", "satisfied_when": "",
          "authored": True}], [], [op], 40)
    assert live == [] and former[0]["why"] == WHY
