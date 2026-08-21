"""Circulation, and the tell rule it exists to feed.

The measurement both live on: a famine month minted 244 witnessable events
and the second-hand spread of every one was zero. Two causes, each with its
fix asserted here — nobody off the watch ever left their room (`errands`),
and the tell slot always went to the freshest co-presence claim
(`tellable`). Neither fix may cost the properties movement already had:
seeded determinism, positions only ever written by something that walked
there, and a quiet control that stands perfectly still.
"""

from __future__ import annotations

from world.charter import (
    charter_places, errands, normalize_charter, run, seed_needs,
    seed_roster, tellable)

from charter_worlds import twin_towns


def _ready(folk=40, rate=None):
    charter = normalize_charter(twin_towns(folk))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    if rate is not None:
        charter["errand_rate"] = rate
    return charter


def _claim(subject, strength, kind=None):
    claim = {"body": subject, "strength": float(strength),
             "as_of_hours": 0.0, "heard_from": None}
    if kind:
        claim["kind"] = kind
    return claim


class TestErrands:
    def test_the_quiet_control_stands_still(self):
        """`errand_rate: 0.0` pins the pre-circulation behaviour: nobody
        but the watch ever moves."""
        from world.charter import step

        charter = _ready(rate=0.0)
        posted_ever = set()
        for index in range(24):
            charter, _ = step(charter, hours=4.0, seed=index)
            posted_ever |= set((charter.get("watch") or {}).values())

        moved = {k for k, n in (charter.get("travelled") or {}).items()
                 if n > 0}
        assert moved <= posted_ever, \
            f"wandered with the rate pinned to zero: {moved - posted_ever}"

    def test_people_actually_circulate_at_the_default(self):
        charter = _ready()
        started = {k: b["place"] for k, b in charter["bodies"].items()}

        after, _ = run(charter, hours=96.0, window=4.0)

        moved = [k for k, n in (after.get("travelled") or {}).items()
                 if n > 0]
        posted = set((after.get("watch") or {}).values())
        assert len(moved) > len(posted), \
            "only the watch ever left home; the rooms are still islands"
        # And nobody teleported: every current place is a room somebody
        # could be -- a berth, a post, or a charter place.
        allowed = set(started.values()) | set(charter_places(after)) | {
            b["berth"] for b in after["bodies"].values()}
        assert all(b["place"] in allowed for b in after["bodies"].values())

    def test_an_errand_goes_where_the_need_is_fed(self):
        charter = _ready()
        key = sorted(charter["bodies"])[2]
        charter["needs"][key]["sustenance"]["fed_by"] = "up_bread"
        reach = {(key, place): 1 for place in charter_places(charter)}

        visits = errands(charter["bodies"], charter["needs"],
                         charter["upkeeps"], {}, charter_places(charter),
                         reach, seed=0, rate=1.0)

        assert visits[key] == charter["upkeeps"]["up_bread"]["place"]

    def test_errands_replay_under_the_same_seed(self):
        charter = _ready()
        reach = {(k, p): 1 for k in charter["bodies"]
                 for p in charter_places(charter)}
        args = (charter["bodies"], charter["needs"], charter["upkeeps"], {},
                charter_places(charter), reach)

        assert errands(*args, seed=7) == errands(*args, seed=7)
        assert errands(*args, seed=7) != errands(*args, seed=8)


class TestTellable:
    def test_the_remarkable_beats_the_stronger_ordinary(self):
        """News of the mill outranks the miller, however well you know the
        miller -- the ordering the 244-events-zero-spread measurement
        forced."""
        held = {"neighbour": _claim("neighbour", 1.0),
                "news:x": _claim("news:x", 0.5, kind="news")}

        assert tellable(held) == "news:x"

    def test_a_departed_figure_is_a_story(self):
        held = {"neighbour": _claim("neighbour", 1.0),
                "traveller": _claim("traveller", 0.6, kind="figure")}

        assert tellable(held) == "traveller"

    def test_the_room_is_the_last_resort(self):
        held = {"here_a": _claim("here_a", 1.0),
                "away_b": _claim("away_b", 0.3)}

        assert tellable(held, visible={"here_a"}) == "away_b"
        assert tellable(held, visible={"here_a", "away_b"}) == "here_a"

    def test_a_visible_figure_is_not_news(self):
        """Nobody reports the traveller to the person standing beside the
        traveller."""
        held = {"traveller": _claim("traveller", 1.0, kind="figure"),
                "away_b": _claim("away_b", 0.3)}

        assert tellable(held, visible={"traveller"}) == "away_b"
