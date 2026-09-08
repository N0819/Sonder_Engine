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

And the read set is STATED ONCE (`scene_memo.SCENE_READS`) rather than
spelled into each key, which is the Section I residual of review C12:
B10 pinned each key to its measured read set, and both measurements
missed a doorway whose barrier and width live on the passage record.
"""

from __future__ import annotations

import copy

from world.scene_memo import SCENE_READS
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


# ---------------------------------------------------------------------------
# ONE STATEMENT OF THE READ SET, SHARED (the Section I residual of C12)
#
# B10 above pinned each key to its MEASURED read set, and a measurement is
# only as wide as what was measured: both keys went on omitting "passages",
# and the sound key also "orientation", "poses" and the beat index. A
# doorway's barrier and width may live on the passage record rather than on
# either edge, and `effective_anchors` resolves every edge through it
# (`resolve_edge` -> `passage_of`), so both fields read the key neither
# named. Both keys now derive from `scene_memo.scene_read_parts`, which is
# the same tuple the read pass fingerprints -- a key spelled by hand is
# short by whatever its author did not think of, and this one was, twice.
# ---------------------------------------------------------------------------

def _passage_scene(barrier, width=None):
    """Two rooms one doorway apart, the doorway's barrier and width living
    on the PASSAGE RECORD rather than on either edge -- the shape a key that
    omits "passages" cannot tell apart."""
    passage = {"rooms": ["hall", "lamp_room"], "barrier": barrier}
    if width is not None:
        passage["width"] = width
    return {
        "rooms": {
            "hall": {"size": "medium", "light": "dark",
                     "adjacent": [{"to": "lamp_room", "dir": "north",
                                   "passage": "p1"}]},
            "lamp_room": {"size": "medium", "light": "bright",
                          "adjacent": [{"to": "hall", "dir": "south",
                                        "passage": "p1"}]},
        },
        "passages": {"p1": passage},
        "positions": {"Ann": "hall", "Bo": "lamp_room"},
        "entities": {}, "stations": {},
    }


def test_light_field_sees_a_doorway_walled_up_on_its_passage_record():
    """Measured: a dark hall lit only by the spill of one doorway kept its
    LIT field when the passage record's barrier flipped to `wall` -- median
    cell 0.02269 where the right answer is 0.0."""
    _clear()
    lit = light_field(_passage_scene("open"), "hall").room_median("hall")
    _clear()
    walled = light_field(_passage_scene("wall"), "hall").room_median("hall")
    assert lit > walled == 0.0
    # The cache warmed on the open doorway must not answer for the walled one.
    _clear()
    light_field(_passage_scene("open"), "hall")
    assert light_field(_passage_scene("wall"), "hall").room_median("hall") == 0.0


def test_light_field_sees_a_doorway_widen():
    """Only a passage record carries a doorway's `width`, and it moved the
    same hall's median 0.02269 -> 0.30501 between 1 pace and 8."""
    _clear()
    narrow = light_field(_passage_scene("open", width=1),
                         "hall").room_median("hall")
    _clear()
    light_field(_passage_scene("open", width=1), "hall")
    wide = light_field(_passage_scene("open", width=8),
                       "hall").room_median("hall")
    assert wide > narrow


def test_sound_field_sees_a_doorway_walled_up_on_its_passage_record():
    """The sibling: a shout across the same doorway went on arriving at
    `full` through a wall, pair gain 0.02117, and a door shut on the
    passage record left the gain at its open value instead of 0.00529."""
    _clear()
    sound_field(_passage_scene("open"), "Ann", turn_idx=1)
    walled = sound_field(_passage_scene("wall"), "Ann", turn_idx=1)
    assert walled.speech_level("Bo", "shout", "Ann") is None

    _clear()
    through_open = sound_field(_passage_scene("open"), "Ann",
                               turn_idx=1).gain_between("Bo", "Ann")
    shut = sound_field(_passage_scene("closed_door"), "Ann",
                       turn_idx=1).gain_between("Bo", "Ann")
    assert shut < through_open


def _probed(scene, name):
    """`scene` with one more thing in the sub-blob `name` -- an addition, so
    every other reader answers exactly as it did, and the only question the
    scene answers differently is the key's."""
    probed = copy.deepcopy(scene)
    current = probed.get(name)
    if isinstance(current, dict):
        probed[name] = dict(current, sonder_probe={"probe": name})
    elif isinstance(current, list):
        probed[name] = list(current) + [{"probe": name}]
    else:
        probed[name] = "sonder_probe"
    return probed


def test_both_keys_move_with_every_sub_blob_the_read_set_names():
    """THE CLASS, not the two instances it was found as: for every scene
    sub-blob `SCENE_READS` names, a scene differing only there must not be
    served the field built for the other one. Asked of the caches rather
    than of the private keys, because there is no one spelling of "the key"
    to ask -- the two siblings define the same private name and the facade
    can carry only one of them.

    Derived from the one statement, a key cannot drift from it; each time
    these were spelled by hand they came out short, and by a different key
    each time.
    """
    for name in SCENE_READS:
        base, probed = _scene(), _probed(_scene(), name)

        _clear()
        first = light_field(base, "a")
        assert first is not None
        assert light_field(probed, "a") is not first, (
            f"the light field's content key ignores scene[{name!r}]")

        _clear()
        first = sound_field(base, "Ana", turn_idx=3)
        assert first is not None
        assert sound_field(probed, "Ana", turn_idx=3) is not first, (
            f"the sound field's content key ignores scene[{name!r}]")
