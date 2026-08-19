"""Perception's scent map graded three ledgers nobody had filled; now it reads them.

`_source_channels` has built `scent_channel_to_sources` for every perceiver on
every beat since the barrier table existed, and the key was read by nobody
(AUDIT_PERCEPTION F4/F5). These drive the whole path instead: a scene with
smells in it, through the real standing-percept builder, out as percepts.

The two firewall questions are the reason this file is long.

1. A muffled scent must ARRIVE muffled. `_SCENT_BARRIER_LEVELS` grades a
   closed door as `muffled` and a wall as nothing; the percept has to carry
   the difference rather than record it.
2. A scent must not defeat a disguise. It does not hand out a name here --
   it hands out a smell, under whatever label this observer's display map
   already earned, which for a disguise that conceals identity is a
   stranger's descriptor.
"""

from agents.perception import _composer_standing_percepts
from agents.composer import observer_display_map


def _scene(barrier="open", light="lit"):
    return {
        "rooms": {
            "kitchen": {"name": "Kitchen", "light": light,
                        "adjacent": [{"to": "yard", "barrier": barrier}]},
            "yard": {"name": "Yard",
                     "adjacent": [{"to": "kitchen", "barrier": barrier}]},
        },
        "positions": {"Ren": "kitchen", "Kesa": "kitchen", "oven_01": "kitchen"},
        "entities": {
            "oven_01": {"name": "Bread Oven", "kind": "fixture",
                        "scent": "hot flour and woodsmoke"},
        },
        "contacts": [],
        "substances": [],
    }


def _kesa(**over):
    body = {"name": "Kesa", "room": "kitchen",
            "appearance": "a tall woman in a leather apron",
            "aliases": [],
            "disguise_known_to": None, "disguise_conceals_identity": None}
    body.update(over)
    return body


#: What `_body_scents` reads off the cards once per stage. A body record
#: carries no scent of its own on purpose: one spelling, so a standing smell
#: cannot be present in one stage's view and absent from the next.
_CARD_SCENTS = {"Kesa": "tallow and cold iron"}


def _percepts(scene, *, observer="Ren", room="kitchen", others=None,
              known=None, senses=None, card_scents=None):
    others = [_kesa()] if others is None else others
    known = known or {observer: ["Kesa"]}
    display_map = observer_display_map(scene, observer, others, known)
    return _composer_standing_percepts(
        scene, {"room": room, "room_name": room, "sense_card": senses},
        observer, others, display_map, known,
        body_scents=_CARD_SCENTS if card_scents is None else card_scents)


def _scents(percepts):
    return [p for p in percepts if p.kind == "scent"]


def _by_smell(percepts, needle):
    return next(p for p in _scents(percepts)
                if needle in p.data.get("scent", ""))


# ------------------------------------------------------- the three ledgers

def test_a_card_scent_reaches_a_body_in_the_room():
    percept = _by_smell(_percepts(_scene()), "tallow")
    assert percept.channel == "smell"
    assert percept.source_label == "Kesa"
    assert percept.fidelity == "full"


def test_an_entity_scent_reaches_the_room_it_stands_in():
    percept = _by_smell(_percepts(_scene()), "hot flour")
    assert percept.channel == "smell"


def test_deposited_matter_reaches_the_room_it_landed_in():
    scene = _scene()
    scene["substances"] = [{
        "source": "Kesa", "source_part": "hand", "substance": "blood",
        "target": "Kesa", "placement": "surface", "target_part": "apron",
        "scent": "wet iron", "substance_id": "s1",
    }]
    assert _by_smell(_percepts(scene), "wet iron")


def test_matter_sealed_inside_something_does_not_smell_out():
    """The ledger already says where the matter is. An `interior` or
    `contained` placement is matter with a body or a vessel between it and
    the room -- the one grading the barrier table cannot do for it, because
    there is no barrier between two rooms to consult."""
    scene = _scene()
    scene["substances"] = [{
        "source": "Kesa", "source_part": "mouth", "substance": "wine",
        "target": "Kesa", "placement": "interior", "target_interior": "stomach",
        "scent": "sour wine", "substance_id": "s1",
    }]
    assert not [p for p in _scents(_percepts(scene))
                if "sour wine" in p.data.get("scent", "")]


def test_a_body_does_not_smell_itself():
    """Habituation, and the honest reason: a standing fact that is true of
    every beat of a character's life is noise in a context window, not a
    percept. Nothing subtracts it downstream, so it is not minted."""
    percepts = _percepts(_scene(), observer="Kesa", others=[
        {"name": "Ren", "room": "kitchen", "appearance": "a young cook",
         "aliases": [], "disguise_known_to": None,
         "disguise_conceals_identity": None}])
    assert not [p for p in _scents(percepts)
                if "tallow" in p.data.get("scent", "")]


# -------------------------------------------------------- question one: grade

def test_a_closed_door_muffles_the_smell_and_strips_its_source():
    scene = _scene(barrier="closed_door")
    percept = _by_smell(_percepts(scene, room="yard"), "tallow")
    assert percept.data["level"] == "muffled"
    assert percept.fidelity == "degraded"
    assert percept.source_label == ""
    assert "Kesa" not in repr(percept)


def test_a_wall_stops_it_entirely():
    scene = _scene(barrier="wall")
    assert not _scents(_percepts(scene, room="yard"))


def test_an_open_door_carries_it_whole():
    scene = _scene(barrier="open_door")
    percept = _by_smell(_percepts(scene, room="yard"), "tallow")
    assert percept.data["level"] == "full"


def test_a_window_passes_sight_and_stops_air():
    """The channels are answered separately and never collapsed: glass is
    the case where the eye wins and the nose loses."""
    scene = _scene(barrier="window")
    assert not _scents(_percepts(scene, room="yard"))


def test_a_full_smell_from_a_body_you_cannot_see_arrives_unattributed():
    """Dark room, same air. The smell crosses; the knowledge of whose it is
    does not, because that was the other channel's to deliver."""
    scene = _scene(light="dark")
    percept = _by_smell(_percepts(scene), "tallow")
    assert percept.data["level"] == "full"
    assert percept.source_label == ""


def test_an_anosmic_card_receives_nothing():
    """The card senses gate applies here as it does everywhere else."""
    senses = [{"channel": "smell", "acuity": "absent"}]
    assert not _scents(_percepts(_scene(), senses=senses))


def test_keen_nose_upgrades_a_muffled_smell_to_a_whole_one():
    senses = [{"channel": "nose", "acuity": "keen"}]
    scene = _scene(barrier="closed_door")
    percept = _by_smell(_percepts(scene, room="yard", senses=senses), "tallow")
    assert percept.data["level"] == "full"


def test_acuity_never_opens_a_wall():
    """`sense_adjusted` caps the one direction that adds: from `none`, scent
    never leaves `none`, because a sealed wall is not something a nose
    penetrates and `none` cannot say which it was."""
    senses = [{"channel": "nose", "acuity": "preternatural"}]
    scene = _scene(barrier="wall")
    assert not _scents(_percepts(scene, room="yard", senses=senses))


# ----------------------------------------------------- question two: disguise

def test_a_scent_does_not_defeat_a_disguise():
    """The observer knows Kesa's name and would use it for a bare face. Under
    a disguise that conceals IDENTITY the smell still arrives -- concealing a
    face does not seal a body -- but it arrives under the label this observer
    earned, which is the stranger's descriptor. The mind may conclude from its
    own memories that this is the smell of someone it knows; the engine does
    not conclude it for them."""
    body = _kesa(disguise_known_to=("someone else",),
                 disguise_conceals_identity=True,
                 appearance="a figure in a hooded cloak")
    percepts = _percepts(_scene(), others=[body])
    percept = _by_smell(percepts, "tallow")
    assert percept.data["scent"] == "tallow and cold iron"
    assert percept.source_label != "Kesa"
    assert "Kesa" not in repr(percept)


def test_a_disguise_that_only_hides_features_keeps_the_name():
    """The other half of the same rule, so the guard cannot be satisfied by
    withholding every name: a disguise that does not claim to conceal
    identity does not conceal it here either."""
    body = _kesa(disguise_known_to=("someone else",),
                 disguise_conceals_identity=False)
    percept = _by_smell(_percepts(_scene(), others=[body]), "tallow")
    assert percept.source_label == "Kesa"


def test_a_stranger_gets_the_smell_and_no_name():
    percepts = _percepts(_scene(), known={"Ren": []})
    percept = _by_smell(percepts, "tallow")
    assert percept.data["scent"] == "tallow and cold iron"
    assert "Kesa" not in repr(percept)


def test_a_substance_never_reports_who_it_came_from():
    """`substance_event_clause` is cause-blind for the recipient and this is
    the standing form of the same rule: matter on a collar says what it
    smells of, never whose body it left."""
    scene = _scene()
    scene["positions"]["Ren"] = "kitchen"
    scene["substances"] = [{
        "source": "Kesa", "source_part": "hand", "substance": "oil",
        "target": "Ren", "placement": "surface", "target_part": "sleeve",
        "scent": "rancid lamp oil", "substance_id": "s1",
    }]
    percept = _by_smell(_percepts(scene), "rancid lamp oil")
    assert "Kesa" not in repr(percept)
