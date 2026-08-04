"""An actor sealed inside something does not get an outside shot of themselves.

`observable` is the intent-free surface of an act as seen FROM OUTSIDE, and the
actor normally receives it in their own view -- rewritten to second person by
`_self_second_person` -- because people can see themselves doing things.

Sealed inside something that stops being true. The surface then describes the
outside of the enclosure, how its wall moves with them, and there is no channel
from inside to that.

Live, chat 60 t18. The declared observable was

    "A tiny lump writhes and squirms beneath the fabric, small limbs pushing
     at the cloth, the shirt shifting and bulging as the lump tries to find a
     way out."

and the actor's own view came back "The lump you make writhes and bulges under
the fabric" -- in darkness, under cloth, two clauses after her own narration
said she could see nothing. Reported from play as: she should not be able to
see the shape she makes.

The rule is keyed on being ENCLOSED, deliberately, and not on darkness or a
failed sight check. Being unable to see in the dark does not stop you knowing
what your own body is doing -- proprioception is not sight -- and suppressing
an actor's own conduct every time the lights went out would be a worse error
than the one this fixes. What an enclosure removes is specifically the outside
view of yourself.

Everyone else's view is untouched: the surface is exactly what they can see,
and that is what it is for.
"""

from __future__ import annotations

import pytest

from agents.perception import _self_cannot_see_own_surface

ACTOR = "Wren"
HOST = "Vessel"
HOST_ID = "vessel_entity"


def _scene(contained=True):
    sc = {
        "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "positions": {ACTOR: "hall", HOST: "hall", "Onlooker": "hall"},
        "entities": {HOST_ID: {"name": HOST, "kind": "person", "aliases": []}},
        "attire": {HOST: {}, ACTOR: {}},
        "scales": {ACTOR: 0.05},
        "contained": {},
    }
    if contained:
        sc["contained"][ACTOR] = {"in": HOST_ID, "mode": "inside"}
    return sc


def _p(name):
    return {"id": "1", "name": name}


class TestTheEnclosedActor:
    def test_their_own_surface_is_withheld(self):
        assert _self_cannot_see_own_surface(_scene(), _p(ACTOR), ACTOR) is True

    def test_it_holds_when_the_actor_is_named_by_entity_id(self):
        """The actor arrives under whichever spelling the beat used."""
        sc = _scene()
        sc["entities"]["wren_entity"] = {"name": ACTOR, "kind": "person"}
        assert _self_cannot_see_own_surface(sc, _p(ACTOR), "wren_entity") is True

    def test_an_open_carry_is_not_an_enclosure(self):
        """Being held in view is not being shut inside anything, and someone
        carried in the open can see themselves perfectly well."""
        sc = _scene()
        sc["contained"][ACTOR] = {"in": HOST_ID, "mode": "held"}
        assert _self_cannot_see_own_surface(sc, _p(ACTOR), ACTOR) is False


class TestEveryoneElseIsUntouched:
    def test_an_onlooker_still_receives_the_surface(self):
        """The surface is exactly what an observer can see, which is what it
        is for. Withholding it from them would be a different bug."""
        assert _self_cannot_see_own_surface(
            _scene(), _p("Onlooker"), ACTOR) is False

    def test_the_host_still_receives_it(self):
        assert _self_cannot_see_own_surface(_scene(), _p(HOST), ACTOR) is False

    def test_an_unenclosed_actor_still_sees_themselves(self):
        assert _self_cannot_see_own_surface(
            _scene(contained=False), _p(ACTOR), ACTOR) is False


class TestItNeverRaises:
    def test_no_scene(self):
        assert _self_cannot_see_own_surface(None, _p(ACTOR), ACTOR) is False

    def test_no_perceiver(self):
        assert _self_cannot_see_own_surface(_scene(), None, ACTOR) is False

    def test_a_nameless_perceiver(self):
        assert _self_cannot_see_own_surface(_scene(), {"id": "1"}, ACTOR) is False


def test_the_gate_runs_before_the_surface_is_injected():
    """A wiring guard rather than a behaviour one: the check has to sit in
    `_inject_onset_sequence` ahead of `_inject_action`, or it is a
    well-tested function nothing calls."""
    import inspect

    from agents import perception
    src = inspect.getsource(perception._inject_onset_sequence)
    assert "_self_cannot_see_own_surface(" in src
    assert src.index("_self_cannot_see_own_surface(") < src.index("_inject_action(")


def test_proprioception_is_not_sight():
    """The rule is keyed on enclosure, never on light. A dark room must not
    stop a character knowing what their own body is doing."""
    import inspect

    from agents import perception
    src = inspect.getsource(perception._self_cannot_see_own_surface)
    assert "hiding_holders_of(" in src
    for lighting in ("light_at", "effective_light", "visual_level_between"):
        assert lighting not in src, lighting
