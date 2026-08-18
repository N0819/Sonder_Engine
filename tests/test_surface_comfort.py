"""Ambient comfort from surfaces (docs/design/DESIGN_SURFACE_COMFORT.md).

Two hard rules are pinned here because losing either silently makes the
feature harmful: comfort NEVER feeds `charge` (a warm bench must not
manufacture an unresolved drive out of contentment), and comfort habituates
(the tenth beat on the cushion is barely felt).
"""

import copy

from mind import psychology_runtime as psych
from world.comfort import comfort_level, rest_affording
from world.survival import tick_vitals, vitals_of


# --- scene scaffolding -----------------------------------------------------

def _scene(**over):
    scene = {
        "rooms": {
            "hall": {"name": "The Hall", "anchors": {
                "hearth": {"desc": "the great hearth", "dir": "n"},
                "corner_bench": {"desc": "a cushioned corner bench"},
            }},
            "cell": {"name": "Bare Cell"},
        },
        "entities": {
            "mira": {"kind": "character", "name": "Mira",
                     "state": {"posture": ""}},
            "bed_1": {"kind": "object", "name": "featherbed",
                      "description": "a deep featherbed heaped with furs"},
            "crate_1": {"kind": "object", "name": "crate",
                        "description": "a rough packing crate"},
            "furnace_1": {"kind": "object", "name": "furnace",
                          "description": "a cold iron furnace"},
        },
        "positions": {"Mira": "hall", "bed_1": "hall", "crate_1": "hall",
                      "furnace_1": "hall"},
        "stations": {},
        "contacts": [],
        "attire": {"Mira": {"wearing": ["a plain cloak"], "state": {}}},
    }
    scene.update(over)
    return scene


def _posture(scene, name, text):
    for ent in scene["entities"].values():
        if ent.get("name") == name:
            ent.setdefault("state", {})["posture"] = text
    return scene


def _contact(scene, actor, target, manner="rest"):
    scene.setdefault("contacts", []).append(
        {"actor": actor, "actor_part": "", "target": target,
         "target_part": "", "manner": manner})
    return scene


def _ambient(state, level, source, *, body_state=None, interoception=None,
             elapsed=1, appraisal=None):
    return psych.resolve_hedonic(
        previous=state, appraisal=appraisal or {},
        interoception=interoception or {}, body_state=body_state or {},
        elapsed_units=elapsed, ambient_comfort=level, comfort_source=source)


# --- derivation: only what the body is verifiably doing --------------------

def test_lying_in_contact_with_soft_surface_is_the_top_tier():
    scene = _contact(_posture(_scene(), "Mira", "lying on the featherbed"),
                     "Mira", "featherbed")
    level, source = comfort_level(scene, "Mira")
    assert level == 0.3
    assert source == "featherbed"
    assert rest_affording(scene, "Mira") is True


def test_seated_contact_is_the_middle_tier():
    scene = _contact(_posture(_scene(), "Mira", "seated on the edge"),
                     "Mira", "featherbed")
    assert comfort_level(scene, "Mira") == (0.2, "featherbed")
    assert rest_affording(scene, "Mira") is False


def test_contact_without_posture_reads_as_seated_not_lying():
    scene = _contact(_scene(), "Mira", "bed_1")
    assert comfort_level(scene, "Mira")[0] == 0.2


def test_standing_at_the_hearth_anchor_is_the_near_tier():
    scene = _scene(stations={"Mira": {"at": "hearth", "near": []}})
    assert comfort_level(scene, "Mira") == (0.1, "the great hearth")


def test_sitting_at_a_cushioned_anchor_uses_posture():
    scene = _posture(
        _scene(stations={"Mira": {"at": "corner_bench", "near": []}}),
        "Mira", "sitting")
    assert comfort_level(scene, "Mira") == (0.2, "a cushioned corner bench")


def test_a_bare_crate_is_not_comfort():
    """Lexicon honesty: contact the vocabulary cannot name says nothing."""
    scene = _contact(_posture(_scene(), "Mira", "lying across it"),
                     "Mira", "crate_1")
    assert comfort_level(scene, "Mira") == (0.0, "")
    assert rest_affording(scene, "Mira") is False


def test_exact_tokens_only_fur_never_fires_on_furnace():
    scene = _contact(_scene(), "Mira", "furnace_1", manner="lean")
    assert comfort_level(scene, "Mira") == (0.0, "")


def test_a_hearth_merely_in_the_room_is_not_verifiable_nearness():
    scene = _scene()
    scene["entities"]["hearth_1"] = {"kind": "object", "name": "hearth"}
    scene["positions"]["hearth_1"] = "hall"
    assert comfort_level(scene, "Mira") == (0.0, "")


def test_a_body_in_a_fur_cloak_is_not_furniture():
    scene = _scene()
    scene["entities"]["sefa"] = {
        "kind": "character", "name": "Sefa",
        "description": "a tall woman wrapped in a heavy fur cloak"}
    scene["positions"]["Sefa"] = "hall"
    scene["attire"]["Sefa"] = {"wearing": ["a heavy fur cloak"], "state": {}}
    _contact(scene, "Mira", "Sefa", manner="lean")
    assert comfort_level(scene, "Mira") == (0.0, "")


def test_comfort_level_never_mutates_the_scene():
    scene = _contact(_posture(_scene(), "Mira", "lying down"),
                     "Mira", "featherbed")
    before = copy.deepcopy(scene)
    comfort_level(scene, "Mira")
    rest_affording(scene, "Mira")
    assert scene == before


# --- the trap: charge is invariant under pure ambient comfort --------------

def test_charge_is_invariant_under_pure_ambient_comfort():
    """Rule 1, pinned directly. Comfort is a RESOLVED state; folding the
    ambient argument back into the `drive` term would manufacture saturated
    bodies out of sitting quietly. If this fails, the refactor that caused it
    reintroduced exactly that."""
    state = {}
    for _ in range(30):
        state = _ambient(state, 0.3, "the featherbed")
    assert state["charge"] == 0.0
    assert state["saturated"] is False
    assert state["pleasure"] > 0.0


def test_ambient_comfort_does_not_change_charge_beside_a_real_stimulus():
    appraisal = {"somatic_impact": {
        "pain": 0.0, "pleasure": 0.5, "why": "the hot bath easing her back"}}
    with_comfort = psych.resolve_hedonic(
        {}, appraisal, {}, {}, 1,
        ambient_comfort=0.3, comfort_source="the bath")
    without = psych.resolve_hedonic({}, appraisal, {}, {}, 1)
    assert with_comfort["charge"] == without["charge"]


# --- the floor itself ------------------------------------------------------

def test_ambient_comfort_floors_the_pleasure_level_with_its_source():
    state = _ambient({}, 0.2, "the cushioned bench")
    assert state["pleasure"] == 0.2
    assert state["source"] == "the cushioned bench"
    assert state["pain"] == 0.0


def test_a_grounded_appraisal_outranks_ambient_comfort_max_not_sum():
    appraisal = {"somatic_impact": {
        "pain": 0.0, "pleasure": 0.8, "why": "her fingers found the splinter"}}
    state = psych.resolve_hedonic(
        {}, appraisal, {"pleasure_sensitivity": 0.5}, {}, 1,
        ambient_comfort=0.2, comfort_source="the bench")
    assert state["pleasure"] == 0.8          # max composition, no stacking
    assert "splinter" in state["source"]


def test_ambient_comfort_passes_through_pleasure_sensitivity():
    stoic = _ambient({}, 0.2, "the bench",
                     interoception={"pleasure_sensitivity": 0.0})
    sybarite = _ambient({}, 0.2, "the bench",
                        interoception={"pleasure_sensitivity": 1.0})
    assert stoic["pleasure"] == 0.1
    assert sybarite["pleasure"] == 0.3


def test_a_chair_is_worth_more_to_a_spent_body():
    fresh = _ambient({}, 0.15, "the bench", body_state={"stamina": 1.0})
    spent = _ambient({}, 0.15, "the bench", body_state={"stamina": 0.0})
    assert fresh["pleasure"] == 0.15
    assert spent["pleasure"] == 0.27         # * (1 + 0.8 * fatigue)
    # Survival off: no vitals, no fatigue term, relief collapses to 1.0 --
    # never a fake fatigue estimate backfilled from beat counts.
    off = _ambient({}, 0.15, "the bench", body_state={})
    assert off["pleasure"] == 0.15


def test_the_ceiling_is_absolute_after_relief_and_sensitivity():
    state = _ambient({}, 0.3, "the featherbed",
                     body_state={"stamina": 0.0},
                     interoception={"pleasure_sensitivity": 1.0})
    assert state["pleasure"] == 0.3


# --- habituation -----------------------------------------------------------

def test_habituation_drives_a_sustained_source_toward_the_floor():
    state = {}
    levels = []
    for _ in range(30):
        state = _ambient(state, 0.2, "the cushioned bench")
        levels.append(state["pleasure"])
    assert levels[0] == 0.2
    assert levels[-1] <= 0.08                # barely felt, not zero
    assert state["comfort_beats"] > 20
    # and the habituated tail never re-inflates
    assert all(b <= a + 1e-9 for a, b in zip(levels, levels[1:]))


def test_a_new_source_resets_habituation():
    state = {}
    for _ in range(12):
        state = _ambient(state, 0.2, "the cushioned bench")
    habituated = state["pleasure"]
    state = _ambient(state, 0.2, "the featherbed")
    assert habituated < 0.1
    assert state["pleasure"] == 0.2
    assert state["comfort_beats"] == 1


def test_leaving_the_surface_clears_the_habituation_state():
    state = _ambient({}, 0.2, "the bench")
    assert state["comfort_beats"] == 1
    away = psych.resolve_hedonic(state, {}, {}, {}, 1)
    assert "comfort_beats" not in away
    assert "comfort_source" not in away
    back = _ambient(away, 0.2, "the bench")
    assert back["pleasure"] == 0.2           # full strength again


def test_no_comfort_keeps_the_hedonic_dict_shape_unchanged():
    state = psych.resolve_hedonic({}, {}, {}, {}, 1)
    assert state == {"pain": 0.0, "pleasure": 0.0, "source": "",
                     "charge": 0.0, "saturated": False,
                     "sustained_beats": 0.0, "stimulus": 0.0}


# --- rest: tick_vitals spends the lying-on-a-soft-surface fact -------------

def _vitals_scene(stamina=0.3):
    scene = _contact(_posture(_scene(), "Mira", "lying on the featherbed"),
                     "Mira", "featherbed")
    scene["vitals"] = {"Mira": {"air": 1.0, "stamina": stamina,
                                "nourishment": 1.0, "injury": 0.0}}
    return scene


def test_lying_on_a_rest_affording_surface_recovers_stamina():
    scene = _vitals_scene(stamina=0.3)
    tick_vitals(scene, 3600)
    assert vitals_of(scene, "Mira")["stamina"] == 0.35   # +0.05/h, not -0.03


def test_rest_rate_is_slower_than_sleep():
    resting = _vitals_scene(stamina=0.3)
    tick_vitals(resting, 3600)
    sleeping = _vitals_scene(stamina=0.3)
    tick_vitals(sleeping, 3600, asleep=["Mira"])
    assert vitals_of(sleeping, "Mira")["stamina"] > \
        vitals_of(resting, "Mira")["stamina"]


def test_declared_exertion_beats_derived_rest():
    scene = _vitals_scene(stamina=0.3)
    tick_vitals(scene, 3600, exerting=["Mira"])
    assert vitals_of(scene, "Mira")["stamina"] < 0.3


def test_a_standing_body_still_drains():
    scene = _scene()
    scene["vitals"] = {"Mira": {"air": 1.0, "stamina": 0.3,
                                "nourishment": 1.0, "injury": 0.0}}
    tick_vitals(scene, 3600)
    assert vitals_of(scene, "Mira")["stamina"] < 0.3


# --- the settling experiment (DESIGN_SURFACE_COMFORT.md section 7) ---------

def test_thirty_beats_parked_on_a_bed():
    """Stamina up, charge unchanged, absorption below 0.25. The fourth
    property (a departure-capable want intact) is the model's to author;
    what the engine can pin is that comfort writes nothing outside the
    hedonic dict for a want to be displaced by."""
    scene = _vitals_scene(stamina=0.3)
    state = {}
    for _ in range(30):
        level, source = comfort_level(scene, "Mira")
        state = psych.resolve_hedonic(
            previous=state, appraisal={}, interoception={},
            body_state=vitals_of(scene, "Mira"), elapsed_units=1,
            ambient_comfort=level, comfort_source=source)
        tick_vitals(scene, 120)              # two minutes a beat
    assert vitals_of(scene, "Mira")["stamina"] > 0.32          # stamina up
    assert state["charge"] == 0.0                              # unchanged
    assert state["saturated"] is False
    assert psych.cognitive_absorption(state) < 0.25            # mind intact
    # sustained_beats/stimulus are resolve_hedonic's own habituation record,
    # written on every beat regardless of comfort. The property under test is
    # that COMFORT adds nothing beyond its two habituation keys.
    assert set(state) <= {"pain", "pleasure", "source", "charge",
                          "saturated", "comfort_beats", "comfort_source",
                          "sustained_beats", "stimulus"}
