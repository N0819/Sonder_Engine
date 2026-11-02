"""A body's height for sight comes from the engine's own posture classes, and a
posture the engine cannot read is not taken to be standing when that decides
whether the body is seen over a fixture.

Audit world_spatial_movement_sight F1 (2026-11-01, LEAK, CONFIRMED): the
posture classifier is an English word list over open free text, and anything it
did not list read `standing` -- the tallest, most visible body. 3,074 of 15,689
posture writes (19.6%) were unclassified, at least 505 plainly low ("reclining"
258, "pinned face-down in the soft tideline sand" 99, "curled" 35, ...), and a
Japanese posture classified as nothing at all. A body the fiction laid down
behind a waist-high counter was therefore SEEN over it.

The class fix reads the engine's own closed classes first (`posture_class` on
the pose, `standing|sitting|kneeling|crouching|lying`, and the class words
themselves in any script's text); a written posture none of that can read is
`unread`, and for the target of a line of sight an unread posture is taken at
the LOWEST class, so a fixture between hides it (the lane's ruling: never
assume standing for the over-a-sill decision). Nothing is changed for a body
whose posture says nothing at all (no pose: standing, as before) or for the
observer's own eye.
"""

from world.spatial import body_visibility, posture_class


def _bar(posture=None, posture_class_word=None):
    pose = {}
    if posture is not None:
        pose["posture"] = posture
    if posture_class_word is not None:
        pose["posture_class"] = posture_class_word
    return {
        "rooms": {"tap": {"name": "the taproom", "extent": {"w": 8, "d": 5},
                          "anchors": {"bar": {"desc": "the bar", "height": "waist",
                                              "footprint": "run", "cell": [3, 0],
                                              "dir": "n"}},
                          "adjacent": []}},
        "positions": {"Ada": "tap", "Bo": "tap"},
        "stations": {"Ada": {"at": None, "near": [], "cell": [3, 4]},
                     "Bo": {"at": None, "near": [], "cell": [3, 0]}},
        "poses": {"Bo": pose} if pose else {},
        "entities": {}, "orientation": {}, "attire": {"Ada": {}, "Bo": {}},
    }


def test_the_engines_own_class_is_read_first():
    assert posture_class(_bar("sprawled out", "sitting"), "Bo") == "sitting"
    assert posture_class(_bar(None, "lying"), "Bo") == "lying"


def test_a_written_posture_nothing_can_read_is_unread_not_standing():
    assert posture_class(_bar("reclining"), "Bo") == "unread"
    assert posture_class(_bar("横たわっている"), "Bo") == "unread"
    assert posture_class(_bar(), "Bo") == "standing"          # nothing written


def test_a_class_word_in_the_text_still_classifies():
    assert posture_class(_bar("lying behind the bar"), "Bo") == "lying"
    assert posture_class(_bar("Seated, elbows on the bar"), "Bo") == "sitting"


# ---- the over-a-counter decision (tests/test_room_geometry.py's taproom) ----

from tests.test_room_geometry import _behind_bar  # noqa: E402


def test_an_unread_low_posture_behind_a_counter_is_hidden():
    for posture in ("reclining against the keg", "curled on her side",
                    "横たわっている"):
        rec = body_visibility(_behind_bar(posture), "P", "Keeper")
        assert not rec["visible"] and rec["occluded_by"] == "the long bar", posture


def test_a_stated_class_decides_over_the_text():
    sc = _behind_bar("leaning on the bar")
    sc["poses"]["Keeper"]["posture_class"] = "standing"
    rec = body_visibility(sc, "P", "Keeper")
    assert rec["visible"] and rec["hidden_below"] == "waist"


def test_nothing_written_is_still_standing_and_the_observers_eye_is_unchanged():
    rec = body_visibility(_behind_bar(), "P", "Keeper")
    assert rec["visible"] and rec["hidden_below"] == "waist"
    sc = _behind_bar()
    sc["poses"]["P"] = {"posture": "reclining"}       # an unread OBSERVER
    assert body_visibility(sc, "P", "Keeper")["visible"]


def test_the_stated_class_survives_the_merge():
    from world.spatial import merge_scene_with_diff
    sc = _behind_bar()
    merged = merge_scene_with_diff(sc, {"poses": {"Keeper": {
        "posture": "sprawled across the boards", "posture_class": "lying"}}})
    assert merged["poses"]["Keeper"]["posture_class"] == "lying"
    junk = merge_scene_with_diff(sc, {"poses": {"Keeper": {
        "posture": "standing", "posture_class": "levitating"}}})
    assert "posture_class" not in junk["poses"]["Keeper"]
