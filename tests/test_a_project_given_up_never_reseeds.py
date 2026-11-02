"""A project the mind gave up out loud never comes back from the card.

An authored project (`psychology.projects`, ids `pa<n>`) is seeded by commit
from the card on any beat its id is in neither `projects` nor
`former_projects` (`persist/commit_memory.py`) -- that check is the whole of
the promise "a project given up never silently re-seeds"
(`docs/design/DESIGN_LONG_TERM_GOALS.md`), and AGENTS.md's "never let the
engine adopt, satisfy or displace one".

The former ledger kept only its newest six endings (`_FORMER_PROJECTS_CAP`),
in both writers that end projects (`apply_project_ops`, `settle_probation`).
So once six later projects had ended -- probation lapses count, and under the
bare contract adoptions are short-lived (UNBUILT_CHARACTERS §1.56: fifteen
held 1-7 beats) -- the record of "the light was automated; I am done with it"
rolled out, and the next commit seeded the lighthouse back, live, with no
word from the mind (review 2026-11-01, mind_affect_psychology F3, reproduced).
"""

from __future__ import annotations

from mind import affect

LIGHT = {"id": "pa1", "project": "Keep the lighthouse lit through the winter",
         "about": "world", "satisfied_when": "", "authored": True,
         "adopted_turn": 0, "last_served_turn": 1}


def _seeds(projects, former):
    """The commit's seeding rule for an authored project (copied, the part
    that decides): seeded unless its id or its words are already held or
    ended."""
    held = {str(p.get("id") or "") for p in projects + former}
    words = {str(p.get("project") or "").strip().casefold() for p in projects + former}
    return LIGHT["id"] not in held and LIGHT["project"].casefold() not in words


def test_seven_later_endings_never_bring_the_lighthouse_back():
    live, former, _w = affect.apply_project_ops(
        [dict(LIGHT)], [], [{"op": "displace", "id": "pa1",
                             "why": "the light was automated; I am done with it"}], 5)
    assert live == [] and [r["id"] for r in former] == ["pa1"]
    for turn in range(6, 13):
        live, former, _w = affect.apply_project_ops(live, former, [{
            "op": "adopt", "project": f"Chart the shoals past the point, stretch {turn}",
            "satisfied_when": "the harbour master posts the new chart"}], turn)
        pid = live[0]["id"]
        live, former, _w = affect.apply_project_ops(
            live, former, [{"op": "displace", "id": pid, "why": "the boat sank"}], turn)
    assert "pa1" in [r["id"] for r in former], "the giving-up is remembered"
    assert not _seeds(live, former)
    assert len([r for r in former if not r["id"].startswith("pa")]) == affect._FORMER_PROJECTS_CAP


def test_probation_lapses_never_roll_the_giving_up_out():
    live, former, _w = affect.apply_project_ops(
        [dict(LIGHT)], [], [{"op": "displace", "id": "pa1", "why": "done with it"}], 5)
    for i in range(7):
        live, former, _w = affect.apply_project_ops(live, former, [{
            "op": "adopt", "project": f"Learn the old songs of the coast, verse {i}",
            "satisfied_when": "the last singer dies"}], 10 + i * 30)
        live, former, _w = affect.settle_probation(live, former, 10 + i * 30 + 25)
    assert live == []
    assert "pa1" in [r["id"] for r in former]


def test_an_ended_authored_project_is_marked_as_one():
    _live, former, _w = affect.apply_project_ops(
        [dict(LIGHT)], [], [{"op": "displace", "id": "pa1", "why": "done with it"}], 5)
    assert former[0].get("authored") is True
