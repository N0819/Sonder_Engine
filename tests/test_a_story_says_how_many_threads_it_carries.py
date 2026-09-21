"""How many causality bubbles a story may hold open at once.

THE DIAL THIS REPLACES (the owner, 2026-09-20): "delete the outdated irrelevant
config ... superseded with charter and the story planner. Replace it with a max
bubble count. as that is different from a max beat count."

`max_offscreen_actors` rationed the off-screen cognition ladder, and
`docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md` is the argument that Charter and
the Writers' Room replaced that tier entirely. What costs now is a BUBBLE: one
character call and one Director resolve per live bubble per committed beat,
forever (`agents/offscreen_beat.py`).

AND IT IS NOT THE CAP THAT WAS REFUSED. On 2026-09-17 the owner struck down a
cap on how many open bubbles ADVANCE per beat -- "I don't think a character
should ever freeze unless they've been made dormant" -- because that stands a
live thread still while its neighbours live and nothing in the fiction explains
which. `OFFSCREEN_BEATS_ARE_UNCAPPED` still holds and this does not touch it.
A cap on how many bubbles EXIST refuses to open the next one, which is a
different act: every bubble that exists runs every beat, and a character
refused one is exactly where every absent character stood before bubbles
existed, with Charter still moving them.
"""

import time

import pytest

from agents.offscreen_beat import OFFSCREEN_BEATS_ARE_UNCAPPED
from story.scene import DEFAULT_INTERACTION_CONFIG, dialogue_config


@pytest.fixture
def cid(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("Threads", "", time.time()))


class TestTheDial:
    def test_the_default_is_three_and_is_named_here(self):
        """`ask before limiting`: the number is in the open, not buried."""
        assert DEFAULT_INTERACTION_CONFIG["max_bubbles"] == 3

    def test_a_story_configured_before_the_rename_keeps_its_answer(self, cid,
                                                                   temp_db):
        """`max_offscreen_actors` asked the same question about the same cost --
        how many absent threads am I paying for -- so a stored value for it is
        read as this one rather than silently reset to the default."""
        temp_db.wset(cid, "dialogue_config", {"max_offscreen_actors": 1})
        assert dialogue_config(cid)["max_bubbles"] == 1

    def test_the_new_key_wins_where_both_are_stored(self, cid, temp_db):
        temp_db.wset(cid, "dialogue_config",
                     {"max_offscreen_actors": 1, "max_bubbles": 5})
        assert dialogue_config(cid)["max_bubbles"] == 5

    def test_a_stored_ladder_value_no_longer_decides_anything(self, cid,
                                                              temp_db):
        """A stored `offscreen_life` is a holdover, not a setting: it rationed a
        tier Charter and the Writers' Room superseded. It is forced back to its
        default so nothing can act on what a story configured years ago.

        THE KEYS ARE STILL PRESENT, and that is measured rather than chosen:
        deleting them outright broke 120 direct readers, several inside the
        commit path, and turns rolled back with
        `offscreen_plans: 'offscreen_life'`. `DESIGN_OFFSCREEN_SUPERSEDED.md`
        §4 says the readers come out first and the keys after.
        """
        from story.scene import (OFFSCREEN_COGNITION_DEFAULT,
                                 OFFSCREEN_LIFE_DEFAULT)
        temp_db.wset(cid, "dialogue_config",
                     {"offscreen_life": "stochastic",
                      "offscreen_cognition": "on", "max_offscreen_actors": 2})
        config = dialogue_config(cid)
        assert config["offscreen_life"] == OFFSCREEN_LIFE_DEFAULT
        assert config["offscreen_cognition"] == OFFSCREEN_COGNITION_DEFAULT
        assert config["max_offscreen_actors"] == 0
        # ...and the cost dial carries the old one's answer over.
        assert config["max_bubbles"] == 2

    @pytest.mark.parametrize("stored,expected", [
        (0, 0), (12, 12), (99, 12), (-4, 0), ("nonsense", 3), (None, 3)])
    def test_it_is_clamped_and_never_throws(self, cid, temp_db, stored,
                                            expected):
        temp_db.wset(cid, "dialogue_config", {"max_bubbles": stored})
        assert dialogue_config(cid)["max_bubbles"] == expected


class TestTheRefusalIsAtTheOpening:
    """A cap on EXISTING bubbles, never on advancing them."""

    def test_advancing_is_still_uncapped(self):
        """The 2026-09-17 ruling stands untouched: every open bubble runs every
        beat. If this ever flips, the third absent character starts freezing
        while the first two live."""
        assert OFFSCREEN_BEATS_ARE_UNCAPPED is True

    def test_the_transition_refuses_rather_than_freezing(self, monkeypatch,
                                                         cid, temp_db):
        """At the cap, the beat opens no new bubble, says so, and leaves every
        open one alone -- and the refusal names the cap so it cannot be read as
        the detector failing."""
        from types import SimpleNamespace
        from world import spatial_frames

        temp_db.wset(cid, "dialogue_config", {"max_bubbles": 2})
        monkeypatch.setattr(spatial_frames, "get_frame", lambda _f: None)
        monkeypatch.setattr(spatial_frames, "detect_merge", lambda *a, **k: None)
        monkeypatch.setattr(spatial_frames, "detect_split", lambda *a, **k: None)
        monkeypatch.setattr(spatial_frames, "detect_couple", lambda *a, **k: None)
        from world import spatial_bubbles
        monkeypatch.setattr(spatial_bubbles, "detect_bubble",
                            lambda *a, **k: {"kind": "bubble",
                                             "characters": ["Emory Vane"],
                                             "rooms": ["mill_race"]})
        import agents.offscreen_beat as ob
        monkeypatch.setattr(ob, "live_bubbles", lambda *a, **k: [11, 12])
        opened = []
        monkeypatch.setattr(spatial_frames, "perform_split",
                            lambda *a, **k: opened.append(k) or 99)

        warnings = []
        ctx = SimpleNamespace(
            chat=SimpleNamespace(id=cid),
            turn=SimpleNamespace(frame_id=None, idx=7),
            add_warning=warnings.append)
        out = spatial_frames.detect_and_reconcile(ctx, 'n')

        assert out["bubble_refused"] == "max_bubbles"
        assert out["open_bubbles"] == 2 and out["max_bubbles"] == 2
        assert not out.get("bubble")
        assert opened == [], "a refusal must not open a frame"
        assert warnings and "Emory Vane" in warnings[0]
        assert "2 of 2" in warnings[0]

    def test_under_the_cap_a_bubble_still_opens(self, monkeypatch, cid,
                                               temp_db):
        from types import SimpleNamespace
        from world import spatial_frames

        temp_db.wset(cid, "dialogue_config", {"max_bubbles": 3})
        monkeypatch.setattr(spatial_frames, "get_frame", lambda _f: None)
        monkeypatch.setattr(spatial_frames, "detect_merge", lambda *a, **k: None)
        monkeypatch.setattr(spatial_frames, "detect_split", lambda *a, **k: None)
        monkeypatch.setattr(spatial_frames, "detect_couple", lambda *a, **k: None)
        from world import spatial_bubbles
        monkeypatch.setattr(spatial_bubbles, "detect_bubble",
                            lambda *a, **k: {"kind": "bubble",
                                             "characters": ["Sal Weatherby"],
                                             "rooms": ["taproom"]})
        import agents.offscreen_beat as ob
        monkeypatch.setattr(ob, "live_bubbles", lambda *a, **k: [11, 12])
        monkeypatch.setattr(spatial_frames, "perform_split", lambda *a, **k: 99)

        ctx = SimpleNamespace(
            chat=SimpleNamespace(id=cid),
            turn=SimpleNamespace(frame_id=None, idx=7),
            add_warning=lambda _m: None)
        out = spatial_frames.detect_and_reconcile(ctx, 'n')
        assert out["bubble"] is True and out["child_frame_id"] == 99

    def test_zero_means_none(self, monkeypatch, cid, temp_db):
        """The "off" the retired cognition toggle spelled as a ladder rung."""
        from types import SimpleNamespace
        from world import spatial_frames

        temp_db.wset(cid, "dialogue_config", {"max_bubbles": 0})
        monkeypatch.setattr(spatial_frames, "get_frame", lambda _f: None)
        monkeypatch.setattr(spatial_frames, "detect_merge", lambda *a, **k: None)
        monkeypatch.setattr(spatial_frames, "detect_split", lambda *a, **k: None)
        monkeypatch.setattr(spatial_frames, "detect_couple", lambda *a, **k: None)
        from world import spatial_bubbles
        monkeypatch.setattr(spatial_bubbles, "detect_bubble",
                            lambda *a, **k: {"kind": "bubble",
                                             "characters": ["Anyone"],
                                             "rooms": ["anywhere"]})
        import agents.offscreen_beat as ob
        monkeypatch.setattr(ob, "live_bubbles", lambda *a, **k: [])
        ctx = SimpleNamespace(
            chat=SimpleNamespace(id=cid),
            turn=SimpleNamespace(frame_id=None, idx=1),
            add_warning=lambda _m: None)
        assert spatial_frames.detect_and_reconcile(ctx, 'n')["bubble_refused"] \
            == "max_bubbles"
