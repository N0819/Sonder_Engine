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


def test_a_standing_presence_splices_a_sentence_shaped_anchor():
    """The presence sentence was the one reader taking an anchor's `desc`
    raw. Chat 123 turn 9: "The Doctor is still at A flat stretch of dark,
    packed sand damp from the receding surf.." -- sentence case and two
    stops, beside a pose sentence that already said "on the sand shelf"."""
    from agents import composer
    sc = {
        "rooms": {"strand": {"name": "Moonlit Strand", "light": "lit",
                             "anchors": {"sand_shelf": {
                                 "desc": "A flat stretch of dark, packed sand "
                                         "damp from the receding surf.",
                                 "dir": "s"}}}},
        "positions": {"Hinami": "strand", "The Doctor": "strand"},
        "stations": {"The Doctor": {"at": "sand_shelf"},
                     "Hinami": {"at": "sand_shelf"}},
        "entities": {}, "orientation": {}, "poses": {},
    }
    body = {"name": "The Doctor", "room": "strand", "appearance": "a thin man",
            "aliases": [], "disguise_known_to": None}
    rows = composer.presence_percepts(sc, "Hinami", [body],
                                      {"The Doctor": "The Doctor"})
    at = [p.data.get("at") for p in rows if p.kind == "presence"]
    assert at and at[0] == ("a flat stretch of dark, packed sand damp from "
                            "the receding surf")
