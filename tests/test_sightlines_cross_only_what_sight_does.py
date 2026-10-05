"""A sightline crosses only what sight does (UNBUILT_PERCEPTION §1.177).

Two walks hand a character rooms beyond the one it can see into, and both
crossed edges no eye crosses -- found by the landscape survey of 2026-10-05
and reproduced twice:

  * `corridor_sightlines` followed a one-way window from its BLIND side:
    behind the mirror, a character was handed the watching room and the
    corridor past it by name while every sight reader said "wall";
  * `sprint_reach` held its sightline open through curtains (a membrane is a
    way through, not a view), so a run offer named the tent three curtains
    away to a mind that had never been in any of them.

And one rendering gap of the same survey: Japanese heard no distant sound.
"""

from __future__ import annotations

from world.spatial import (corridor_sightlines, spatial_rel, sprint_reach,
                           visible_adjacent_rooms)


def _mirror():
    """An observation room watching a cell through a one-way window, with a
    corridor running on past the observation room."""
    return {"rooms": {
        "obs": {"name": "Observation Room", "light": "lit", "adjacent": [
            {"to": "cell", "barrier": "one_way_window", "dir": "e",
             "sight_from": "obs"},
            {"to": "back", "barrier": "open", "dir": "w"}]},
        "cell": {"name": "Interrogation Cell", "light": "lit", "adjacent": []},
        "back": {"name": "Back Corridor", "light": "lit", "adjacent": [
            {"to": "obs", "barrier": "open", "dir": "e"},
            {"to": "stairs", "barrier": "closed_door", "dir": "w"}]},
        "stairs": {"name": "Stairs", "light": "lit", "adjacent": []}},
        "positions": {"Suspect": "cell", "Cop": "obs"}, "stations": {}}


def _booth():
    """A booth watching a long hall through a one-way window: the seeing side
    looks down a straight line of three rooms."""
    def hall(i, last=False):
        adj = [{"to": "booth" if i == 1 else "hall%d" % (i - 1), "barrier": "open",
                "dir": "w"}]
        if not last:
            adj.append({"to": "hall%d" % (i + 1), "barrier": "open", "dir": "e"})
        return {"name": "Hall %d" % i, "light": "lit", "adjacent": adj}
    rooms = {"booth": {"name": "Booth", "light": "lit", "adjacent": [
        {"to": "hall1", "barrier": "one_way_window", "dir": "e", "sight_from": "booth"}]},
        "hall1": hall(1), "hall2": hall(2), "hall3": hall(3, last=True)}
    rooms["hall1"]["adjacent"][0]["barrier"] = "one_way_window"
    rooms["hall1"]["adjacent"][0]["sight_from"] = "booth"
    return {"rooms": rooms, "positions": {}, "stations": {}}


def test_behind_the_mirror_no_room_beyond_it_is_named():
    sc = _mirror()
    assert spatial_rel(sc, "cell", "obs")["barrier"] == "wall"
    assert visible_adjacent_rooms(sc, "cell") == []
    lines = corridor_sightlines(sc, "cell")
    named = {a.get("room") for line in lines for a in line.get("along") or ()}
    assert lines == [] and "Observation Room" not in named


def test_the_watching_side_still_looks_down_the_line():
    sc = _booth()
    (line,) = corridor_sightlines(sc, "booth")
    assert line["dir"] == "e" and line["terminus"] == "dead_end"
    assert [a["room"] for a in line["along"]] == ["Hall 1", "Hall 2"]
    assert all(line["dir"] != "w" for line in corridor_sightlines(sc, "hall1"))


def _tents(barrier):
    def tent(i, last=False):
        adj = [] if i == 1 else [{"to": "t%d" % (i - 1), "barrier": barrier, "dir": "w"}]
        if not last:
            adj.append({"to": "t%d" % (i + 1), "barrier": barrier, "dir": "e"})
        return {"name": "Tent %d" % i, "light": "lit", "size": "small", "adjacent": adj}
    return {"rooms": {"t1": tent(1), "t2": tent(2), "t3": tent(3), "t4": tent(4, last=True)},
            "positions": {"Ada": "t1"}, "stations": {}}


def test_a_run_offer_never_names_rooms_behind_curtains_it_never_saw():
    offers = sprint_reach(_tents("membrane"), "t1", known_rooms=[])
    reached = {room for offer in offers for room in offer["path"]}
    assert not reached & {"t2", "t3", "t4"}


def test_a_run_offer_still_runs_down_a_line_it_can_see():
    (offer,) = sprint_reach(_tents("open"), "t1", known_rooms=[])
    assert offer["path"][:2] == ["t2", "t3"]


def test_curtains_it_has_been_through_are_remembered_ground():
    (offer,) = sprint_reach(_tents("membrane"), "t1", known_rooms=["t2", "t3"])
    assert offer["path"][:2] == ["t2", "t3"]


def test_japanese_hears_a_distant_sound():
    from agents.composer import distant_sound_percepts, render_view
    records = [{"level": "plain", "bearing": {"phrase": "北の方から"},
                "character": "鐘の音"}]
    ja = render_view(distant_sound_percepts(records), mode="player",
                     full_render=True, language="ja").text
    en = render_view(distant_sound_percepts(
        [{"level": "plain", "bearing": {"phrase": "From the north"},
          "character": "a bell"}]), mode="player", full_render=True,
        language="en").text
    assert "a bell" in en
    assert "鐘の音" in ja and "北の方から" in ja
