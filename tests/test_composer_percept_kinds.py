"""The list of percept kinds was read by nothing, so it went two kinds stale.

`PERCEPT_KINDS` declared twelve. `pose_percepts` and `body_part_percepts`
mint two more, and `Percept.kind` was a bare `str` with no validation, so
nothing anywhere compared the declaration against the practice. A vocabulary
nobody checks is not a vocabulary -- it is a comment that happens to be
syntactically valid Python.

The repair is the check, not a longer list: a second hand-maintained list of
one thing is what the audit found, and adding the two missing names without
wiring the list up leaves the next two to drift the same way.
"""

import pytest

from agents.composer import CHANNELS, PERCEPT_KINDS, Percept, _STANDING_ORDER


def test_an_undeclared_kind_is_refused():
    with pytest.raises(ValueError):
        Percept(kind="rumour", channel="sight")


def test_an_undeclared_channel_is_refused():
    with pytest.raises(ValueError):
        Percept(kind="presence", channel="telepathy")


def test_every_declared_kind_can_be_built():
    for kind in PERCEPT_KINDS:
        for channel in CHANNELS:
            assert Percept(kind=kind, channel=channel).kind == kind


def test_the_standing_order_names_only_declared_kinds():
    """The drift that actually happened. `_STANDING_ORDER` is read on every
    render and already carried both missing names; `PERCEPT_KINDS` is read
    on no path and did not, which is exactly why only the unread one was
    wrong."""
    undeclared = sorted(set(_STANDING_ORDER) - set(PERCEPT_KINDS))
    assert not undeclared, (
        f"kinds the renderer orders but the vocabulary does not declare: "
        f"{undeclared}")


def test_the_live_builders_mint_declared_kinds():
    """The two that went missing, minted the way production mints them."""
    import agents.composer as composer

    scene = {
        "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "positions": {"Ada": "hall"},
        "poses": {"Ada": {"posture": "kneeling"}},
    }
    poses = composer.pose_percepts(scene, "Ada", [], {})
    assert poses, "the pose builder produced nothing to check"
    for percept in poses:
        assert percept.kind in PERCEPT_KINDS
