"""A speaker in another room raises their voice over the din where THEY stand,
whether or not their room has furniture with an authored height.

Audit world_spatial_sound F5 (2026-11-01, CONFIRMED WRONG-SCENE):
`SoundField._field_for` -- the sibling field a cross-room pair reads the
SPEAKER's noise from -- gated on `room_has_geometry`, the FOV layer's opt-in
(an anchor with an authored height), while `sound_field` itself gates on
`_room_grid_exists` (a size tier, an extent or any anchors), widened
2026-09-06. 479 of the owner's 1,093 live rooms have a field by the wide gate
and none by the narrow one, so a speaker standing in one never got
`speaker_din_db`: their voice was never Lombard-raised over their own room's
din, and a normal line to its addressee a few paces off through an open
doorway graded `none` where the din rule says `fragment`.
"""

from world.spatial import sound_field, spatial_rel_between


def _two_taprooms():
    def room(name, edge):
        return {"name": name, "exposure": "enclosed", "extent": {"w": 6, "d": 6},
                "anchors": {}, "adjacent": [edge]}
    return {
        "rooms": {"tap": room("the taproom", {"to": "snug", "barrier": "open_door", "dir": "e"}),
                  "snug": room("the snug", {"to": "tap", "barrier": "open_door", "dir": "w"})},
        "positions": {"A": "tap", "B": "snug"},
        "stations": {"A": {"cell": [3, 3]}, "B": {"cell": [2, 3]}},
        "entities": {}, "poses": {}, "orientation": {}, "contained": {},
    }


def _crowds():
    return [{"uid": "drinkers", "room_uid": "tap", "band": "a few dozen"},
            {"uid": "snuggers", "room_uid": "snug", "band": "a few dozen"}]


def test_the_speakers_own_din_is_stamped_across_rooms():
    sc = _two_taprooms()
    field = sound_field(sc, "B", crowds=_crowds())
    assert field is not None
    rel = spatial_rel_between(sc, "B", "A", sound=field)
    assert rel.get("din_db") is not None
    assert rel.get("speaker_din_db") is not None
