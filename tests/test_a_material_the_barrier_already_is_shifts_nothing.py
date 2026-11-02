"""A material that names what a barrier class already IS shifts nothing:
a glass window is a window, iron bars are bars.

Audit world_spatial_sound F4 (2026-11-01, CONFIRMED WRONG-SCENE, live chat
172): `_MATERIAL_SOUND_STEPS` gives `glass` -1, and `_material_shifted_barrier`
walked a `window` one rung "more solid" on `_SOUND_LADDER` -- to `wall`. The
step exists for a door made of glass (`closed_door` -> `window`); on a window it
counted the pane twice. The planner's card invites it ("material? ... glass")
and chat 172 holds six window edges with `material: glass`: a loud voice that
fragments through a bare window was `none` through a glass one, the at-the-pane
rows were unreachable, the garden was not laid on the bedroom's acoustic grid
at all, and the far field charged a wall's 45 dB for a pane's 28. The same
double count put iron bars on the shut-door rung.
"""

from world.spatial import (_edge_loss_db, _material_shifted_barrier, hear_level,
                           spatial_rel_between)

VOLUMES = ("mutter", "whisper", "normal", "loud", "shout")


def test_the_class_material_shifts_nothing():
    assert _material_shifted_barrier("window", "glass") == "window"
    assert _material_shifted_barrier("window", "Glass") == "window"
    assert _material_shifted_barrier("bars", "iron") == "bars"
    assert _material_shifted_barrier("bars", "steel") == "bars"


def test_a_material_that_is_not_the_class_still_shifts():
    assert _material_shifted_barrier("closed_door", "glass") == "window"
    assert _material_shifted_barrier("closed_door", "paper") == "bars"
    assert _material_shifted_barrier("window", "paper") == "closed_door"
    assert _material_shifted_barrier("open_door", "stone") == "bars"


def test_the_far_field_prices_a_glass_window_as_a_window():
    assert _edge_loss_db({"to": "x", "barrier": "window", "material": "glass"}) \
        == _edge_loss_db({"to": "x", "barrier": "window"})


def _rooms(material=None):
    e1 = {"to": "b", "barrier": "window", "dir": "e"}
    e2 = {"to": "a", "barrier": "window", "dir": "w"}
    if material:
        e1["material"] = e2["material"] = material
    def room(edges):
        return {"name": "room", "size": "medium", "exposure": "enclosed",
                "adjacent": edges, "anchors": {"c": {"desc": "a counter",
                                                     "dir": "n", "height": "waist"}}}
    return {"rooms": {"a": room([e1]), "b": room([e2])},
            "positions": {"S": "a", "L": "b"}, "stations": {}, "orientation": {},
            "poses": {}, "entities": {}, "contained": {}}


def test_a_voice_through_a_glass_window_is_heard_as_through_a_window():
    bare = spatial_rel_between(_rooms(), "L", "S")
    glass = spatial_rel_between(_rooms("glass"), "L", "S")
    assert {v: hear_level(glass, v) for v in VOLUMES} \
        == {v: hear_level(bare, v) for v in VOLUMES}
