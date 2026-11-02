"""A frame split reads and writes the frame it splits, carries what the party
knows, and a reunion keeps what the home party did to its own rooms.

Audit world_spatial_truth (2026-11-01):

* F7 (CONFIRMED latent CORRUPTION): `perform_split` read and wrote `scene`
  through the AMBIENT frame (`wget`/`wset`) beside an explicit
  `parent_frame_id` it used for every other key -- split off a past frame with
  no active frame set, the PRESENT's scene was partitioned and written back,
  and the past frame's scene was never touched.
* F10 (CONFIRMED): `knowledge_circles` was not seeded into the child, so in a
  bubble `effective_circles` read a blank overlay and the knowledge gate
  withheld lore she was initiated into; and `perform_merge` never unioned it
  back, so a circle joined while away was lost at reunion.
* F2 (CONFIRMED CORRUPTION): both sides hold the whole map since 2026-09-17,
  and the reunion's default rule let the away copy win EVERY room -- the home
  party's shut door and new cellar way reverted to the split instant.
"""

from core.db import wget, wget_for_frame, wset, wset_for_frame
from mind.knowledge_circles import join_circle, story_circles
from tests.test_the_bubble_radius_is_rooms_walked import _story


def _split(cid, parent=None):
    from world import spatial_frames
    return spatial_frames.perform_split(cid, parent, 0, bubble=True,
                                        away_names=["Tamamo"])


def test_a_split_off_another_frame_touches_only_that_frame(temp_db):
    from core.frames import create_frame
    cid = _story(temp_db, tamamo_at="r7")
    present_before = wget(cid, "scene", {})
    past = create_frame(cid, label="Before", ordinal=-1, kind="past")
    wset_for_frame(cid, "scene", {"rooms": present_before["rooms"], "entities": {},
                                  "comms": {}, "positions": {"Hinami": "r0",
                                                             "Tamamo": "r6"}}, past)
    child = _split(cid, past)
    assert wget(cid, "scene", {}) == present_before
    assert "Tamamo" not in wget_for_frame(cid, "scene", past, {})["positions"]
    assert wget_for_frame(cid, "scene", child, {})["positions"] == {"Tamamo": "r6"}


def test_circles_ride_the_split_and_come_home(temp_db):
    from world import spatial_frames
    cid = _story(temp_db, tamamo_at="r7")
    join_circle(cid, "tamamo", "the order", turn_idx=60)
    child = _split(cid)
    assert [r["circle"] for r in story_circles(cid, "tamamo", child)] == ["the order"]
    join_circle(cid, "tamamo", "the river guild", turn_idx=61, frame_id=child)
    assert spatial_frames.perform_merge(cid, None, child, 62) is not None
    assert {r["circle"] for r in story_circles(cid, "tamamo")} == {
        "the order", "the river guild"}


def test_the_home_partys_own_rooms_survive_the_reunion(temp_db):
    from world import spatial_frames
    cid = _story(temp_db, tamamo_at="r7")
    child = _split(cid)
    home = wget(cid, "scene", {})
    for edge in home["rooms"]["r0"]["adjacent"]:
        if edge["to"] == "r1":
            edge["barrier"] = "closed_door"
    home["rooms"]["cellar"] = {"name": "cellar", "adjacent": [{"to": "r0", "barrier": "open"}]}
    home["rooms"]["r0"]["adjacent"].append({"to": "cellar", "barrier": "open"})
    wset(cid, "scene", home)
    assert spatial_frames.perform_merge(cid, None, child, 4) is not None
    merged = wget(cid, "scene", {})
    r0 = {e["to"]: e["barrier"] for e in merged["rooms"]["r0"]["adjacent"]}
    assert r0.get("r1") == "closed_door"
    assert r0.get("cellar") == "open"
    assert merged["positions"].get("Tamamo") == "r7"
