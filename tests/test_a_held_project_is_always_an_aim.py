"""A project the mind holds is always among the aims its read-back offers.

The read-back asks which aim a want serves (`want:serves`, `held_back:serves`)
and how the beat touched each aim (`impact:<a>`), over `Holding.aims` -- built
drive, then the steering intentions, then the held projects, and cut at
`MAX_AIMS` (5). Whenever the drive and the steering intentions filled the cap
(always at `broad`/`wide` with a full ledger; the `ordinary` rung steers four)
every project was cut (review 2026-11-01, mind_affect_psychology F8,
reproduced: drive + four intentions + p1 -> options a0..a4, p1 nowhere). A
probationary project then cannot earn its three serving beats and lapses at
24; an established one reads adrift for ever. Projects are the tier meant to
outrank intentions, and there are at most two: the cap stays, and is filled
around them.
"""

from __future__ import annotations

from mind import affect, character_jev as jev


def _aims(intentions=4, projects=1):
    out = [{"kind": "drive", "id": "drive", "text": "keep the light"}]
    out += [{"kind": "intention", "id": f"i{n}", "text": f"errand {n}"}
            for n in range(1, intentions + 1)]
    out += [{"kind": "project", "id": f"p{n}", "text": f"long work {n}"}
            for n in range(1, projects + 1)]
    return out


def test_every_held_project_is_offered_within_the_cap():
    offered = jev.aims_offered(_aims(4, affect.PROJECT_CAP))
    ids = [a["id"] for a in offered]
    assert len(offered) == jev.MAX_AIMS
    assert {"p1", "p2"} <= set(ids)
    assert ids[0] == "drive"
    assert ids == ["drive", "i1", "i2", "p1", "p2"], "the order is kept; the last errands give way"


def test_nothing_changes_when_everything_fits():
    aims = _aims(2, 1)
    assert jev.aims_offered(aims) == aims
