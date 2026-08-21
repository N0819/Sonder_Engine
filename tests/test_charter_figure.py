"""Figures: the player as a claim subject, and what that must never become.

The gap this closes: for a background NPC to interact believably ACROSS
encounters it must accumulate a view of the player — first-hand where it saw
them, second-hand where it was told, decaying, capable of being wrong. Before
`charter_figure`, `minds` could only hold claims about bodies and news, so
the person the story is about was the one thing nobody off-screen could know.

And the boundary, each half a test: a figure is never a body (not rostered,
not planned, not blamed), and a figure never grows a mind here (its knowledge
lives in the engine's own character machinery; a copy would be a second
representation drifting from the first).
"""

from __future__ import annotations

from world.charter import (
    figure_spread, known_figures, normalize_charter, run, scene_ledger,
    seed_needs, seed_roster, stale_figure_claims)

from charter_worlds import twin_towns


def _ready(folk=60, figure_place=None):
    charter = normalize_charter(twin_towns(folk))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    charter["active_places"] = sorted(
        {b["place"] for b in charter["bodies"].values()})
    if figure_place is not None:
        charter["figures"] = {"traveller": {"place": figure_place,
                                            "surface": {"cloak": "grey"}}}
        charter = normalize_charter(charter)
    return charter


def _a_place_with_people(charter):
    counts = {}
    for body in charter["bodies"].values():
        counts[body["place"]] = counts.get(body["place"], 0) + 1
    return max(sorted(counts), key=lambda p: counts[p])


class TestAViewAccumulates:
    def test_bodies_present_come_to_know_the_figure_first_hand(self):
        charter = _ready()
        place = _a_place_with_people(charter)
        charter["figures"] = {"traveller": {"place": place}}
        charter = normalize_charter(charter)

        after, _ = run(charter, hours=4.0, window=4.0)

        holders, secondhand = figure_spread(after["minds"], "traveller")
        assert holders > 0, "the figure stood in a room and nobody saw it"
        assert secondhand == 0
        seen = [k for k, b in after["bodies"].items()
                if b["place"] == place and "traveller" in after["minds"][k]]
        assert seen, "nobody at the figure's own place holds a claim"

    def test_word_of_the_figure_travels_second_hand(self):
        """A figure claim rides tell/ask like any other claim: heads that
        never shared a room with the traveller come to know OF it."""
        charter = _ready()
        place = _a_place_with_people(charter)
        charter["figures"] = {"traveller": {"place": place}}
        charter = normalize_charter(charter)

        after, _ = run(charter, hours=48.0, window=4.0)

        holders, secondhand = figure_spread(after["minds"], "traveller")
        assert secondhand > 0, "nobody ever heard of the traveller"
        assert holders > secondhand, "no first-hand sighting survived"

    def test_the_view_can_be_wrong(self):
        """The claim records where the figure was SEEN. When the figure
        moves on, every held claim goes stale -- which is what recognition
        being real costs."""
        charter = _ready()
        place = _a_place_with_people(charter)
        charter["figures"] = {"traveller": {"place": place}}
        charter = normalize_charter(charter)
        charter, _ = run(charter, hours=8.0, window=4.0)

        charter["figures"]["traveller"]["place"] = ""
        after, _ = run(charter, hours=4.0, window=4.0)

        wrong = stale_figure_claims(after["minds"], after["figures"])
        assert wrong, "the traveller left and every head updated by magic"

    def test_minds_forget_the_figure_the_ledger_does_not_rule(self):
        """Personal decay applies: a figure gone long enough is forgotten,
        with no special machinery doing the forgetting."""
        charter = _ready()
        place = _a_place_with_people(charter)
        charter["figures"] = {"traveller": {"place": place}}
        charter = normalize_charter(charter)
        charter, _ = run(charter, hours=8.0, window=4.0)
        assert figure_spread(charter["minds"], "traveller")[0] > 0

        charter["figures"]["traveller"]["place"] = ""
        after, _ = run(charter, hours=160.0, window=4.0)

        assert figure_spread(after["minds"], "traveller")[0] == 0


class TestNeverABody:
    def test_a_figure_is_not_rostered_planned_or_blamed(self):
        charter = _ready()
        place = _a_place_with_people(charter)
        charter["figures"] = {"traveller": {"place": place}}
        charter = normalize_charter(charter)

        after, _ = run(charter, hours=96.0, window=4.0)

        assert "traveller" not in after["roster"]
        assert "traveller" not in set((after.get("watch") or {}).values())
        assert "traveller" not in (
            (after.get("politics") or {}).get("blame") or {})

    def test_a_figure_never_grows_a_mind(self):
        charter = _ready()
        place = _a_place_with_people(charter)
        charter["figures"] = {"traveller": {"place": place}}
        charter = normalize_charter(charter)

        after, _ = run(charter, hours=96.0, window=4.0)

        assert "traveller" not in after["minds"], \
            "a second representation of the player's knowledge"


class TestRecognitionInTheLedger:
    def test_the_returning_figure_is_known_not_strange(self):
        """The scene a player walks back into: whoever met them shows them
        under `knows_here`; whoever did not shows them a stranger."""
        charter = _ready()
        place = _a_place_with_people(charter)
        charter["figures"] = {"traveller": {"place": place}}
        charter = normalize_charter(charter)
        charter, _ = run(charter, hours=4.0, window=4.0)

        view = scene_ledger(charter, place)

        assert view["figures_here"] == ["traveller"]
        met = [k for k, p in view["presences"].items()
               if "traveller" in p["knows_here"]]
        assert met, "nobody in the room recognises the figure standing there"
        entry = view["presences"][met[0]]["knows_here"]["traveller"]
        assert entry["figure"] is True and entry["firsthand"] is True
        assert entry["believes_present"] is True

    def test_a_head_that_never_met_the_figure_calls_it_a_stranger(self):
        charter = _ready()
        place = _a_place_with_people(charter)
        charter["figures"] = {"traveller": {"place": place}}
        charter = normalize_charter(charter)

        view = scene_ledger(charter, place)

        strangers = {s for p in view["presences"].values()
                     for s in p["strangers_here"]}
        assert "traveller" in strangers

    def test_known_figures_reads_one_heads_view_only(self):
        charter = _ready()
        place = _a_place_with_people(charter)
        charter["figures"] = {"traveller": {"place": place}}
        charter = normalize_charter(charter)
        charter, _ = run(charter, hours=4.0, window=4.0)

        witness_key = next(k for k, b in charter["bodies"].items()
                           if b["place"] == place
                           and "traveller" in charter["minds"].get(k, {}))
        held = known_figures(charter["minds"], witness_key)

        assert held and held[0]["body"] == "traveller"
        assert held[0]["surface"] == {}
