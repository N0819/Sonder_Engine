"""An act that touches a room's own fixture happened, and a person the scene
stands is somebody whose name an observer may lack.

Playerless Aldermill round 4 replay (2026-09-23): a sluice tender working the
jack in plain view of the yard, and the woman watching him braced on the
dock, were both un-seen -- each contact's fixture endpoint verified as
"lacks established endpoints", so the world was read as refusing the act. On
another beat a charter body's name reached the watcher's own pose, and her
memory, because the last scrub listed only the cast.
"""
from world.causal_verification import _known


def _scene():
    return {"rooms": {"mill_race": {"name": "Mill Race",
                                    "anchors": {"jack_lever": {"kind": "fixture"}}}},
            "positions": {"Wimelard": "mill_race"}, "entities": {}}


def test_a_fixture_is_a_known_endpoint():
    assert _known(_scene(), "jack_lever")
    assert not _known(_scene(), "the moon")


def test_the_scrub_roster_lists_every_body_the_scene_stands():
    from agents.perception import _identity_roster
    scene = {"entities": {
        "Master Kenelmund": {"name": "Master Kenelmund", "kind": "person",
                             "aliases": ["Kenelmund"]},
        "jack_lever": {"name": "jack lever", "kind": "fixture"}}}
    roster = _identity_roster("Nobody", "", [], scene=scene)
    names = [r["name"] for r in roster]
    assert "Master Kenelmund" in names and "jack lever" not in names
