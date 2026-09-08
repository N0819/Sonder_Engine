"""The scene read pass: what it memoises, and everything that ends it.

Review C12. The spatial derivations are pure functions of the scene, and a
composer region asks each of them for the same answer 5-9 times per
(observer, body). `world/scene_memo.py` lets a region that only READS say
so and pay once. The mechanism is a memo, so what needs pinning is not the
speed -- it is every way the memo must STOP answering, because a memo that
answers one derivation too long is a wrong scene, not a slow one.

Measured on chat 117's stored 38-room, 22-body scene, one stage's worth of
sight, stations, anchors and fields: 1.27-1.61 s before, 0.21-0.27 s after
(tools/bench/spatial_derivation.py). Composing every observer's presence,
pose and environment percepts off the same scene went 0.514 s -> 0.087 s,
byte-identical.
"""
from __future__ import annotations

import logging

import pytest

from world.scene_memo import (SCENE_READS, clear_scene_memo, scene_memo,
                              scene_read_pass)
from world.spatial import (anchor_cells, effective_anchors, effective_station,
                           light_at, proximity_rel, visual_level_between)


@pytest.fixture(autouse=True)
def _no_leftover_pass():
    clear_scene_memo()
    yield
    clear_scene_memo()


def _scene():
    return {
        "rooms": {
            "hall": {"name": "the Hall", "size": "large", "light": "lit",
                     "anchors": {"bar": {"desc": "the long bar", "dir": "n"}},
                     "adjacent": [{"to": "kitchen", "barrier": "open_door",
                                   "dir": "e"}]},
            "kitchen": {"name": "the Kitchen", "light": "lit",
                        "anchors": {"stove": {"desc": "the stove", "dir": "n"}},
                        "adjacent": []},
        },
        "positions": {"Reya": "hall", "Kai": "hall"},
        "entities": {},
        "stations": {"Reya": {"at": "bar"}, "Kai": {"at": "bar"}},
        "contacts": [],
    }


def _counted():
    calls = []

    def build():
        calls.append(1)
        return len(calls)

    return calls, build


# ---- the pass is the whole scope ------------------------------------------

def test_no_pass_no_memo():
    """The default is today's behaviour: every call derives.

    This is the property that keeps a caller which mutates a scene in place
    and reads it back correct -- three tests in the sound, light and room
    suites do exactly that, and an always-on memo failed all three.
    """
    sc = _scene()
    calls, build = _counted()
    assert scene_memo(sc, "k", build) == 1
    assert scene_memo(sc, "k", build) == 2
    assert len(calls) == 2


def test_inside_a_pass_a_question_is_asked_once():
    sc = _scene()
    calls, build = _counted()
    with scene_read_pass(sc):
        assert scene_memo(sc, "k", build) == 1
        assert scene_memo(sc, "k", build) == 1
    assert len(calls) == 1


def test_a_distinct_question_is_its_own_answer():
    sc = _scene()
    calls, build = _counted()
    with scene_read_pass(sc):
        assert scene_memo(sc, ("sight", "Reya", "Kai"), build) == 1
        assert scene_memo(sc, ("sight", "Kai", "Reya"), build) == 2
    assert len(calls) == 2


def test_the_cache_dies_with_the_pass():
    sc = _scene()
    calls, build = _counted()
    with scene_read_pass(sc):
        scene_memo(sc, "k", build)
    with scene_read_pass(sc):
        assert scene_memo(sc, "k", build) == 2
    assert len(calls) == 2


def test_a_nested_pass_joins_the_outer_one_and_does_not_end_it():
    sc = _scene()
    calls, build = _counted()
    with scene_read_pass(sc):
        scene_memo(sc, "k", build)
        with scene_read_pass(sc):
            assert scene_memo(sc, "k", build) == 1
        # the inner exit must not release the outer pass's cache
        assert scene_memo(sc, "k", build) == 1
    assert scene_memo(sc, "k", build) == 2


def test_an_exception_still_ends_the_pass():
    sc = _scene()
    calls, build = _counted()
    with pytest.raises(RuntimeError):
        with scene_read_pass(sc):
            scene_memo(sc, "k", build)
            raise RuntimeError("boom")
    assert scene_memo(sc, "k", build) == 2


def test_a_pass_answers_for_that_scene_object_alone():
    """Identity, not equality: two scenes that read alike are two scenes."""
    sc, other = _scene(), _scene()
    calls, build = _counted()
    with scene_read_pass(sc):
        assert scene_memo(sc, "k", build) == 1
        assert scene_memo(other, "k", build) == 2
        assert scene_memo(other, "k", build) == 3


def test_a_pass_over_a_non_dict_scene_memoises_nothing():
    calls, build = _counted()
    with scene_read_pass(None):
        assert scene_memo(None, "k", build) == 1
        assert scene_memo(None, "k", build) == 2


# ---- the self-check -------------------------------------------------------

def test_a_region_that_writes_is_reported(caplog):
    """A pass is a claim about the region, and the claim is checked.

    A mutation inside a pass is a bug in where the pass was opened, not a
    condition to absorb: the answers already handed out may have been
    derived from the scene as it stood before the write. So the close
    re-fingerprints and says so.
    """
    sc = _scene()
    with caplog.at_level(logging.WARNING, logger="world.scene_memo"):
        with scene_read_pass(sc):
            sc["rooms"]["hall"]["light"] = "dark"
    assert any("changed inside a read pass" in r.message for r in caplog.records)


def test_a_region_that_only_reads_is_silent(caplog):
    sc = _scene()
    with caplog.at_level(logging.WARNING, logger="world.scene_memo"):
        with scene_read_pass(sc):
            visual_level_between(sc, "Reya", "Kai")
            light_at(sc, "Reya")
            anchor_cells(sc, "hall")
    assert not caplog.records


def test_the_read_set_names_the_beat_key():
    """`SCENE_READS` spells "beat_idx"; `world.spatial` re-exports it.

    Two spellings of one key is exactly the drift this repo keeps finding,
    so the two are pinned together here rather than trusted to agree.
    """
    from world.spatial import BEAT_KEY
    assert BEAT_KEY in SCENE_READS


class _RecordingScene(dict):
    """A scene that says which top-level sub-blobs were read off it."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.read = set()

    def get(self, key, default=None):
        self.read.add(key)
        return dict.get(self, key, default)

    def __getitem__(self, key):
        self.read.add(key)
        return dict.__getitem__(self, key)

    def __contains__(self, key):
        self.read.add(key)
        return dict.__contains__(self, key)


def _furnished_scene():
    """A scene that exercises every key `SCENE_READS` names.

    Deliberately not the small `_scene()` above: it carries a passage, a
    body contained inside another body, stations, poses, orientation,
    weather and a beat index, because a key the fixture never reaches is a
    key the read-set test cannot pin. "passages" is the case that proves
    it -- chat 117's real 38-room scene has no `passages` at all, so the
    original patch's byte-for-byte diff over it was true and still missed
    that `effective_anchors` reads the key (review C12 rework).
    """
    return _RecordingScene({
        "rooms": {
            "hall": {
                "name": "the Hall", "size": "large", "light": "lit",
                "extent": {"w": 14, "d": 12},
                "anchors": {
                    "bar": {"desc": "the long bar", "dir": "n",
                            "height": "waist", "footprint": "run",
                            "opacity": "solid"},
                    "lamp": {"desc": "the lamp", "dir": "s",
                             "height": "waist", "light": "lit"},
                },
                "adjacent": [{"to": "kitchen", "barrier": "open_door",
                              "dir": "e", "passage": "p1"}],
            },
            "kitchen": {
                "name": "the Kitchen", "size": "small", "light": "dim",
                "anchors": {"stove": {"desc": "the stove", "dir": "n",
                                      "height": "waist"}},
                "adjacent": [],
            },
            "Reya_throat": {"name": "Reya's throat", "size": "tiny",
                            "anchors": {}, "adjacent": [],
                            "parent_entity": "Reya"},
        },
        "positions": {"Reya": "hall", "Kai": "hall", "Mira": "kitchen",
                      "Tam": "Reya_throat"},
        "entities": {"lamp": {"state": {"lit": True}}},
        "stations": {"Reya": {"at": "bar"}, "Kai": {"at": "bar"},
                     "Mira": {"at": "stove"}},
        "orientation": {"Reya": {"facing": "n"}, "Kai": {"facing": "s"}},
        "poses": {"Kai": {"posture": "sitting", "support": "bar"}},
        "contacts": [{"a": "Reya", "b": "Kai", "relation": "holding"}],
        "contained": {"Tam": {"holder": "Reya", "interior": "throat"}},
        "crossings": [],
        "passages": {"p1": {"rooms": ["hall", "kitchen"],
                            "barrier": "open_door", "name": "the door"}},
        "day_phase": "night",
        "weather": {"sky": "clear"},
        "beat_idx": 7,
    })


def _ask_every_memoised_derivation(sc):
    """Every question the read pass memoises, over the whole fixture."""
    from world.spatial import light_field, sound_field
    for room in ("hall", "kitchen", "Reya_throat"):
        effective_anchors(sc, room)
        effective_anchors(sc, room, derive=True)
        anchor_cells(sc, room)
        light_field(sc, room)
    bodies = ("Reya", "Kai", "Mira", "Tam")
    for body in bodies:
        effective_station(sc, body)
        sound_field(sc, body)
    for a in bodies:
        for b in bodies:
            if a != b:
                visual_level_between(sc, a, b)
                proximity_rel(sc, a, b)


def test_the_read_set_covers_what_the_derivations_read():
    """SCENE_READS is a claim about the SEVEN DERIVATIONS, so check it
    against them and not only against a constant.

    The stamp is what the pass re-fingerprints on close, and the module's
    own argument is that a stamp short by a key would miss a mutation. It
    WAS short by one: `effective_anchors` resolves every edge through
    `spatial_barriers.resolve_edge` -> `passage_of`, so it reads
    `scene["passages"]`, and inside a pass a flipped passage barrier was
    both un-invalidated and unreported (review C12 rework; the flip itself
    is pinned below). Pinning the tuple to BEAT_KEY could not catch that
    and no diff over a stored scene could either, because neither stored
    scene carries a passage -- only asking the derivations what they touch
    can.
    """
    sc = _furnished_scene()
    _ask_every_memoised_derivation(sc)
    assert sc.read <= set(SCENE_READS), (
        "a memoised derivation reads a scene key SCENE_READS does not stamp, "
        "so a write to it inside a read pass would be neither invalidated "
        f"nor reported: {sorted(sc.read - set(SCENE_READS))}")


def test_the_fixture_reaches_every_key_the_read_set_names():
    """The other half: a stamped key no fixture exercises is how the last
    omission survived, so the fixture is pinned to the tuple too. Widening
    SCENE_READS means widening `_furnished_scene` to reach the new key."""
    sc = _furnished_scene()
    _ask_every_memoised_derivation(sc)
    assert set(SCENE_READS) <= sc.read, (
        "SCENE_READS names a key the fixture never makes a derivation read, "
        f"so nothing pins it: {sorted(set(SCENE_READS) - sc.read)}")


def test_a_passage_flip_inside_a_pass_is_reported(caplog):
    """The mutation the stamp used to miss.

    A doorway's barrier can live on the passage rather than on either edge,
    and `effective_anchors` reads it through `resolve_edge`. The memo is
    still allowed to answer with the pre-flip value -- a pass PROMISES no
    writes, and the answers already handed out cannot be recalled -- but the
    close must say the promise was broken. Before "passages" joined
    SCENE_READS this closed silently.
    """
    sc = {
        "rooms": {
            "a": {"name": "A", "anchors": {},
                  "adjacent": [{"to": "b", "barrier": "open", "dir": "e",
                                "passage": "p1"}]},
            "b": {"name": "B", "anchors": {}, "adjacent": []},
        },
        "positions": {},
        "passages": {"p1": {"rooms": ["a", "b"], "barrier": "open"}},
    }
    assert effective_anchors(sc, "a")["door:b"]["desc"] == "the opening"
    with caplog.at_level(logging.WARNING, logger="world.scene_memo"):
        with scene_read_pass(sc):
            effective_anchors(sc, "a")
            sc["passages"]["p1"]["barrier"] = "closed_door"
    assert any("changed inside a read pass" in r.message
               for r in caplog.records)
    # and the flip is a real one: outside a pass it changes the answer.
    assert effective_anchors(sc, "a")["door:b"]["desc"] == "the doorway"


# ---- the derivations answer the same, pass or no pass ---------------------

def test_every_memoised_derivation_answers_identically_inside_a_pass():
    sc = _scene()
    bare = {
        "sight": visual_level_between(sc, "Reya", "Kai"),
        "prox": proximity_rel(sc, "Reya", "Kai"),
        "anchors": effective_anchors(sc, "hall"),
        "cells": anchor_cells(sc, "hall"),
        "station": effective_station(sc, "Reya"),
    }
    with scene_read_pass(sc):
        assert visual_level_between(sc, "Reya", "Kai") == bare["sight"]
        assert proximity_rel(sc, "Reya", "Kai") == bare["prox"]
        assert effective_anchors(sc, "hall") == bare["anchors"]
        assert anchor_cells(sc, "hall") == bare["cells"]
        assert effective_station(sc, "Reya") == bare["station"]


def test_the_sight_memo_keys_on_both_bodies():
    """The firewall reading of the key: it is the OBJECTIVE derivation, and
    it names the observer as well as the target, so no observer's answer can
    be served to another."""
    sc = _scene()
    sc["positions"]["Mira"] = "kitchen"
    with scene_read_pass(sc):
        assert visual_level_between(sc, "Reya", "Kai") == \
            visual_level_between(sc, "Kai", "Reya")
        near = visual_level_between(sc, "Reya", "Kai")
        far = visual_level_between(sc, "Reya", "Mira")
    sc_again = _scene()
    sc_again["positions"]["Mira"] = "kitchen"
    assert visual_level_between(sc_again, "Reya", "Kai") == near
    assert visual_level_between(sc_again, "Reya", "Mira") == far


def test_a_memoised_answer_is_copied_out_where_it_is_mutable():
    """A caller may add to what it is handed, and the next asker must not
    see the addition: `effective_station` grows a `near` list, and
    `effective_anchors` and `anchor_cells` hand back dicts."""
    sc = _scene()
    with scene_read_pass(sc):
        station = effective_station(sc, "Reya")
        station["near"].append("Kai")
        station["at"] = "stove"
        assert effective_station(sc, "Reya")["near"] == []
        assert effective_station(sc, "Reya")["at"] == "bar"

        anchors = effective_anchors(sc, "hall")
        anchors.pop("bar")
        assert "bar" in effective_anchors(sc, "hall")

        cells = anchor_cells(sc, "hall")
        cells.pop("bar", None)
        assert "bar" in anchor_cells(sc, "hall")
