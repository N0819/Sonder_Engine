"""A field memo's key names everything its derivation reads (review B10).

The sound field and the light field are both memoised per (scene, room), and
both keys were narrower than the derivation behind them: the sound key held
no `crossings` at all, and both keys projected the entity table down to the
entities that emit -- while `effective_station` reads EVERY entity's names
and aliases to seat a body at the room feature it is touching, and reads a
body's live threshold crossing to stand it in the doorway it came through.
A body's cell is where its sound is made and where its lamp hangs, so an
entity that neither sounds nor shines still moves both fields.

The sound field carried a second guard on top -- `cached.scene is scene` --
which is the wrong question twice over: it cannot see a scene mutated in
place (the same object, and every one of these cases is one), and it refuses
a scene that is equal in everything the derivation reads. The rule this file
pins: THE KEY IS THE WHOLE READ SET, AND THE KEY ALONE DECIDES.
"""

from __future__ import annotations

import copy

from world.spatial import (
    _FIELD_CACHE,
    _SOUND_FIELD_CACHE,
    light_field,
    sound_field,
)


def _room(anchors, adjacent=()):
    return {"name": "the room", "size": "medium", "exposure": "enclosed",
            "light": "dim", "adjacent": list(adjacent), "anchors": dict(anchors)}


def _scene(*, contact=True):
    """One room with a brazier feature and a doorway east, a body `Cy`
    holding the noisy/lit thing, and a listener `Ana`.

    `Cy` carries no authored station: where Cy stands is derived, either
    from the contact with the brazier ENTITY (whose alias is what ties it to
    the room's `brazier` anchor) or, with `contact=False`, from the doorway
    of a live threshold crossing. The two are the same branch of
    `effective_station` and the authored contact wins, so the crossing case
    asks for a scene without one.
    """
    east = {"to": "b", "barrier": "open_door", "dir": "e"}
    west = {"to": "a", "barrier": "open_door", "dir": "w"}
    return {
        "rooms": {
            "a": _room({"brazier": {"desc": "a brazier", "dir": "n",
                                    "height": "waist"},
                        "east": {"desc": "the east door", "dir": "e"}},
                       [east]),
            "b": _room({"shelf": {"desc": "a shelf", "dir": "s",
                                  "height": "waist"}}, [west]),
        },
        "positions": {"Ana": "a", "Cy": "a", "brazier_1": "a", "thing": "a"},
        "stations": {"Ana": {"cell": [0, 0]}},
        "orientation": {},
        "poses": {},
        "entities": {
            "brazier_1": {"name": "the iron brazier", "aliases": ["brazier"]},
            "thing": {"name": "the pump", "sound_source": "loud",
                      "light_source": "lit", "steadiness": "steady"},
        },
        "contained": {"thing": {"in": "Cy"}},
        "contacts": [{"actor": "Cy", "target": "brazier_1",
                      "relation": "hold"}] if contact else [],
        "crossings": {},
        "day_phase": "night",
    }


def _clear():
    _SOUND_FIELD_CACHE.clear()
    _FIELD_CACHE.clear()


def _sound_cell(scene):
    field = sound_field(scene, "Ana", turn_idx=3)
    assert field is not None
    placed = [s for s in field.sources if s["id"] == "thing"]
    assert placed, "the sound source is on the field"
    return placed[0]["at"]


def _lit_cells(scene):
    lf = light_field(scene, "a")
    assert lf is not None
    return sorted(lf.per_source["thing"])


# ---------------------------------------------------------------------------
# The sound field
# ---------------------------------------------------------------------------

def test_sound_field_sees_a_crossing_appear():
    """`crossings` was read by the derivation and absent from the key."""
    _clear()
    scene = _scene(contact=False)
    before = _sound_cell(scene)
    # The same scene object, mutated in place the way one beat's readers
    # would see it: Cy is now standing in the doorway it came through.
    scene["crossings"]["Cy"] = {"from": "b", "to": "a", "beats": 1}
    assert _sound_cell(scene) != before


def test_sound_field_sees_an_entity_that_makes_no_sound():
    """The key projected the entity table down to its sound sources, and the
    brazier makes none -- but its alias is what seats Cy at the brazier."""
    _clear()
    scene = _scene()
    before = _sound_cell(scene)
    scene["entities"]["brazier_1"]["aliases"] = []
    assert _sound_cell(scene) != before


def test_sound_field_is_reused_for_a_scene_equal_in_everything_it_reads():
    """The identity test the key made unnecessary: a scene that answers the
    key identically answers every reader identically, so it gets the field
    that was already built."""
    _clear()
    scene = _scene()
    first = sound_field(scene, "Ana", turn_idx=3)
    assert first is not None
    assert sound_field(copy.deepcopy(scene), "Ana", turn_idx=3) is first


# ---------------------------------------------------------------------------
# The light field -- the same key, the same gap in it
# ---------------------------------------------------------------------------

def test_light_field_sees_an_entity_that_gives_no_light():
    """`_cache_key` kept only the light sources; the brazier is not one."""
    _clear()
    scene = _scene()
    before = _lit_cells(scene)
    scene["entities"]["brazier_1"]["aliases"] = []
    assert _lit_cells(scene) != before
