"""A way through that is not a way to look through.

The barrier vocabulary could say "see it but do not reach it" (`window`,
`bars`) and could not say the reverse. Every passable barrier -- `open`,
`open_door` -- was also transparent, so a doorway a body could push through
had to be authored as one sight passed through too.

That gap showed up hardest on entity interiors, whose exterior doorway is
DERIVED rather than authored (spatial.apply_transit_dock_edges). An open
interior always derived `open_door`, so walking into an enclosure granted
everyone in the room outside a clear line of sight into it: the occupant
became more exposed by entering a space than by standing in the open, and
the perception layer -- correctly trusting has_visual -- pasted their
appearance into every outside observer's view.

`membrane` is that missing rung: passable, never see-through, sound muffled.
`enclosure: "membrane"` selects it for an entity interior in both states.
"""

import copy

import pytest

from spatial import (
    apply_transit_dock_edges,
    effective_light,
    has_visual,
    hear_level,
    merge_scene_with_diff,
    normalize_barrier,
    passable_route_exists,
    sight_level,
    spatial_rel,
    visible_adjacent_rooms,
)


def _tent_scene(enclosure="membrane", hatch=None, light=None):
    """A camp with a flap-doored shelter standing in it.

    Deliberately mundane: the mechanism is about what an opening is made of,
    not about what kind of thing has an interior.
    """
    interior = {
        "name": "Shelter Interior",
        "desc": "A cramped space under canvas.",
        "adjacent": [{"to": "camp", "barrier": "open_door", "distance": "near"}],
        "parent_entity": "shelter",
    }
    if light is not None:
        interior["light"] = light
    state = {}
    if hatch is not None:
        state["hatch"] = hatch
    return {
        "rooms": {
            "shelter_interior": interior,
            "camp": {"name": "Camp", "desc": "An open clearing.", "adjacent": []},
        },
        "entities": {
            "shelter": {
                "name": "Shelter",
                "kind": "structure",
                "enclosure": enclosure,
                "state": state,
            }
        },
        "positions": {"shelter": "camp", "Ada": "shelter_interior",
                      "Bo": "camp"},
    }


# --- the barrier itself -----------------------------------------------------

def test_membrane_is_passable_but_not_see_through():
    """The one combination the vocabulary could not previously express."""
    rel = {"same_room": False, "barrier": "membrane", "distance": "near",
           "light": "lit"}
    assert sight_level(rel) == "none"
    assert has_visual(rel) is False

    scene = {"rooms": {
        "a": {"adjacent": [{"to": "b", "barrier": "membrane"}]},
        "b": {"adjacent": []},
    }}
    assert passable_route_exists(scene, "a", "b") is True


def test_membrane_is_the_inverse_of_window():
    """window: seen, not reached. membrane: reached, not seen."""
    window = {"same_room": False, "barrier": "window", "distance": "near",
              "light": "lit"}
    membrane = {"same_room": False, "barrier": "membrane", "distance": "near",
                "light": "lit"}
    scene = {"rooms": {
        "a": {"adjacent": [{"to": "b", "barrier": "window"}]},
        "b": {"adjacent": []},
    }}

    assert has_visual(window) is True
    assert passable_route_exists(scene, "a", "b") is False
    assert has_visual(membrane) is False


@pytest.mark.parametrize("alias", [
    "membrane", "curtain", "curtained_doorway", "tent flap", "flap",
    "bead curtain", "veil", "drape",
])
def test_soft_opening_aliases_normalize_to_membrane(alias):
    """These used to degrade to `wall` (the unrecognized-barrier fallback),
    which stops bodies as well as sight -- so the only authorable option was
    to lie and call them `open_door`."""
    assert normalize_barrier(alias) == "membrane"


def test_adding_a_barrier_did_not_move_what_materials_shift_onto():
    """Guard on a trap this change walked straight into.

    _SOUND_LADDER is walked by RELATIVE steps, so inserting a rung silently
    changes what its neighbours land on. Putting `membrane` between `bars` and
    `closed_door` moved a paper screen -- a closed_door one grade more open --
    off `bars` and onto `membrane`, quietly making every paper screen in every
    scene harder to overhear through. `membrane` is deliberately not on the
    ladder; anything added to it must re-check these.
    """
    paper = {"same_room": False, "barrier": "closed_door", "distance": "near",
             "material": "paper"}
    assert hear_level(paper, "normal") == "full"

    metal = {"same_room": False, "barrier": "closed_door", "distance": "near",
             "material": "metal"}
    assert hear_level(metal, "normal") == "none"

    # A membrane is off the ladder, so a material has nothing to shift.
    for material in ("paper", "metal", "soundproof", ""):
        rel = {"same_room": False, "barrier": "membrane", "distance": "near",
               "material": material}
        assert hear_level(rel, "normal") == "fragment"


def test_membrane_muffles_rather_than_blocks_sound():
    """Opaque is not soundproof: a raised voice crosses, an ordinary one
    arrives as a fragment, a muttered one does not survive."""
    rel = {"same_room": False, "barrier": "membrane", "distance": "near"}
    assert hear_level(rel, "shout") == "full"
    assert hear_level(rel, "loud") == "full"
    assert hear_level(rel, "normal") == "fragment"
    assert hear_level(rel, "mutter") == "none"


# --- derived interior doorways ---------------------------------------------

def test_membrane_enclosure_overrides_an_authored_transparent_doorway():
    """The regression. The interior's authored edge says `open_door`; the
    enclosure says the way in is opaque. The enclosure is the structural
    fact and must win -- preserving the authored barrier is exactly what
    left an occupant visible from outside."""
    sc = _tent_scene()
    assert apply_transit_dock_edges(sc) is True

    rel = spatial_rel(sc, "shelter_interior", "camp")
    assert rel["barrier"] == "membrane"
    assert has_visual(rel) is False


def test_occupant_of_a_membrane_interior_is_not_visible_from_outside():
    """Stated the way perception asks it: can Bo, standing in the camp, see
    Ada, who has stepped inside."""
    sc = _tent_scene()
    apply_transit_dock_edges(sc)

    rel = spatial_rel(sc, sc["positions"]["Bo"], sc["positions"]["Ada"])
    assert has_visual(rel) is False
    # ...and still hears her raised voice through the canvas.
    assert hear_level(rel, "shout") == "full"


def test_membrane_interior_stays_passable_from_outside():
    """Concealment is not imprisonment: the flap is still the way in."""
    sc = _tent_scene()
    apply_transit_dock_edges(sc)
    assert passable_route_exists(sc, "camp", "shelter_interior") is True


def test_membrane_interior_is_opaque_when_closed_too():
    """A membrane is opaque in BOTH states -- unlike a lid, which is the
    whole distinction the enclosure field now carries."""
    sc = _tent_scene(hatch="closed")
    apply_transit_dock_edges(sc)

    rel = spatial_rel(sc, "shelter_interior", "camp")
    assert has_visual(rel) is False
    assert passable_route_exists(sc, "camp", "shelter_interior") is False


def test_unlit_membrane_interior_gets_no_spill_from_the_room_outside():
    """effective_light spills only through a SIGHT barrier, so closing the
    sight channel closes the light channel with it. An unlit interior behind
    a membrane stays dark instead of being lifted to `dim` by the lit space
    on the other side -- which would have restored `shapes` sight and put
    the occupant back on view."""
    sc = _tent_scene(light="dark")
    sc["rooms"]["camp"]["light"] = "lit"
    apply_transit_dock_edges(sc)

    assert effective_light(sc, "shelter_interior") == "dark"
    assert sight_level(spatial_rel(sc, "camp", "shelter_interior")) == "none"


def test_membrane_interior_is_not_listed_as_a_visible_adjacent_room():
    sc = _tent_scene()
    apply_transit_dock_edges(sc)
    assert "shelter_interior" not in visible_adjacent_rooms(sc, "camp")


def test_derivation_is_idempotent_and_survives_a_merge():
    sc = _tent_scene()
    apply_transit_dock_edges(sc)
    once = copy.deepcopy(sc)
    apply_transit_dock_edges(sc)
    assert sc == once

    merged = merge_scene_with_diff(copy.deepcopy(sc), {})
    assert spatial_rel(merged, "shelter_interior", "camp")["barrier"] == "membrane"


# --- everything that is NOT a membrane is unchanged -------------------------

@pytest.mark.parametrize("enclosure", [None, "", "opaque"])
def test_lidded_interiors_keep_their_authored_open_doorway(enclosure):
    """A hatch or a lid standing open genuinely is see-through. Only the
    membrane case changes; vehicles and chests derive exactly as before."""
    sc = _tent_scene(enclosure=enclosure)
    apply_transit_dock_edges(sc)

    rel = spatial_rel(sc, "shelter_interior", "camp")
    assert rel["barrier"] == "open_door"
    assert has_visual(rel) is True


def test_transparent_enclosure_still_sees_out_when_shut():
    sc = _tent_scene(enclosure="transparent", hatch="closed")
    apply_transit_dock_edges(sc)

    rel = spatial_rel(sc, "shelter_interior", "camp")
    assert rel["barrier"] == "window"
    assert has_visual(rel) is True


# --- the declaration has to survive being redeclared ------------------------

def test_enclosure_can_be_set_on_an_entity_that_already_exists():
    """`_merge_entity` copies the fields it knows and leaves the rest at
    whatever the existing record held -- so a field missing from that map can
    only ever be set at CREATION. `enclosure` was missing from it, which made
    an interior authored see-through see-through forever: the Director could
    declare the correction every beat and the merge dropped it every beat.
    """
    scene = {"entities": {"shelter": {"name": "Shelter", "kind": "structure"}}}
    merged = merge_scene_with_diff(
        scene, {"entities": {"shelter": {"enclosure": "membrane"}}})
    assert merged["entities"]["shelter"]["enclosure"] == "membrane"
    assert merged["entities"]["shelter"]["name"] == "Shelter"   # not clobbered


def test_a_redeclaration_that_omits_enclosure_does_not_erase_it():
    """Silence is not an erasure -- the rule the rest of the merge already
    follows. A pose-only diff must not strip what the thing is made of."""
    scene = {"entities": {"shelter": {"name": "Shelter",
                                      "enclosure": "membrane"}}}
    merged = merge_scene_with_diff(
        scene, {"entities": {"shelter": {"state": {"hatch": "open"}}}})
    assert merged["entities"]["shelter"]["enclosure"] == "membrane"


def test_light_source_has_the_same_durability():
    scene = {"entities": {"lamp": {"name": "Lamp", "kind": "object"}}}
    merged = merge_scene_with_diff(
        scene, {"entities": {"lamp": {"light_source": "lit"}}})
    assert merged["entities"]["lamp"]["light_source"] == "lit"

    again = merge_scene_with_diff(
        merged, {"entities": {"lamp": {"state": {"lit": True}}}})
    assert again["entities"]["lamp"]["light_source"] == "lit"
