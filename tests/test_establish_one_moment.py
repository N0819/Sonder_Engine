"""Establishment states ONE moment, and everything it declares is somewhere.

An opening passage usually narrates a sequence rather than describing a
standing situation -- a character-card greeting always does, because that is
what a first message IS. Observed live (chat 53, "Run!"): a greeting whose
five beats were cornered / rescued / hauled inside / lever thrown / turns to
look committed as a snapshot with each body frozen at a DIFFERENT beat. The
player stood mid-motion at the doors (beat 2) while the character stood at the
console with the lever already thrown (beat 4); the creature the whole opening
was about kept a present-tense "weapon charging with a rising whine" from beat
0, in no room at all; and `contacts` was empty, so the hand that seized her
wrist and hauled her through the door had never touched her.

The moment-choosing itself is a prompt rule and cannot be tested here. What CAN
be made structural is the rest, and this file covers exactly that:

- an entity declared and left unplaced is a hard validation error (it is
  excluded from co-presence by construction, so it can never be perceived or
  act);
- an opening can express a standing hold at all, through the same contact_ops
  path every later beat uses;
- a body that arrives already inside something is not recorded as having just
  climbed into it.
"""
import json

from schemas import semantic_output_errors, validate_llm_output
from spatial import THRESHOLD_CROSSING_BEATS, crossing_of
from spatial_frames import infer_threshold_crossings


def _establish(**over):
    out = {
        "location": "A dead-end alley",
        "time": "night",
        "rooms": {"alley": {"name": "Alley", "desc": "Wet brick.", "adjacent": []}},
        "positions": {"Ada": "alley"},
        "entities": {},
    }
    out.update(over)
    return out


# --- an entity that exists must be somewhere ------------------------------

def test_an_unplaced_entity_is_a_semantic_error():
    """The live failure: a creature with a full description and a live
    present-tense state, in no room, which `agents/background.py` then drops
    from co-presence ("unplaced presence: cannot prove co-presence, leave
    out") -- so it can never be perceived and never acts."""
    errors = semantic_output_errors("director_establish", _establish(
        entities={"hunter": {"name": "The Metal Hunter", "kind": "creature",
                             "description": "Armoured, advancing."}},
    ))
    assert any("hunter" in e for e in errors), errors


def test_placing_the_entity_clears_the_error():
    errors = semantic_output_errors("director_establish", _establish(
        entities={"hunter": {"name": "The Metal Hunter", "kind": "creature"}},
        positions={"Ada": "alley", "hunter": "alley"},
    ))
    assert errors == []


def test_a_room_the_party_has_left_still_counts_as_placed():
    """The point of the rule: a body left behind is ELSEWHERE, not nowhere."""
    errors = semantic_output_errors("director_establish", _establish(
        rooms={"alley": {"name": "Alley", "desc": "Wet brick.", "adjacent": []},
               "inside": {"name": "Inside", "desc": "Elsewhere.", "adjacent": []}},
        entities={"hunter": {"name": "The Metal Hunter", "kind": "creature"}},
        positions={"Ada": "inside", "hunter": "alley"},
    ))
    assert errors == []


def test_positions_keyed_by_display_name_satisfies_the_check():
    """Readers accept either key, so validation must too -- otherwise a
    correctly-placed entity aborts the opening on a keying convention."""
    errors = semantic_output_errors("director_establish", _establish(
        entities={"hunter": {"name": "The Metal Hunter", "kind": "creature"}},
        positions={"Ada": "alley", "The Metal Hunter": "alley"},
    ))
    assert errors == []


def test_a_portable_creature_may_be_carried_rather_than_placed():
    """Inventory is not `positions`; a familiar in a pocket is not unplaced."""
    errors = semantic_output_errors("director_establish", _establish(
        entities={"rat": {"name": "a pocket rat", "kind": "animal",
                          "portable": True}},
    ))
    assert errors == []


def test_a_bodiless_voice_is_never_expected_in_a_room():
    """Positioning a ship's computer is the category error
    scene.is_ubiquitous_entity exists to prevent."""
    by_flag = semantic_output_errors("director_establish", _establish(
        entities={"comp": {"name": "Computer", "kind": "agent",
                           "ubiquitous": True}},
    ))
    by_kind = semantic_output_errors("director_establish", _establish(
        entities={"comp": {"name": "Computer", "kind": "ship_ai"}},
    ))
    assert by_flag == [] and by_kind == []


def test_a_portal_spans_two_rooms_and_is_in_neither():
    """`state.link` is the engine's two-room shape (the Director is told to
    author a gate that way); demanding a single position for one is wrong."""
    errors = semantic_output_errors("director_establish", _establish(
        entities={"gate": {"name": "The Gate", "kind": "spirit",
                           "state": {"link": {"rooms": ["alley", "inside"],
                                              "phase": "open"}}}},
    ))
    assert errors == []


# --- the check must not fail the openings that already work ---------------

def test_furniture_and_fixtures_are_not_required_to_have_a_room():
    """The measurement that set this rule's scope. 17 of 48 live scenes carry
    an unplaced non-portable entity -- 53 in total, all inert: framed
    diplomas, a shoe rack, a captain's chair, a bell tower, ward doors, a
    day-room television, `location`-kind stand-ins for a whole starship.
    Requiring a room of every one would have killed roughly a third of
    openings to tidy up furniture, and none of them was ever going to act."""
    inert = {
        "diploma": {"name": "A framed diploma", "kind": "fixture"},
        "rack": {"name": "A shoe rack", "kind": "container"},
        "chair": {"name": "The captain's chair", "kind": "fixture"},
        "tower": {"name": "The bell tower", "kind": "structure"},
        "ward_door": {"name": "The ward door", "kind": "portal"},
        "tv": {"name": "The day-room television", "kind": "technology"},
        "ship": {"name": "USS Enterprise", "kind": "location"},
        "shuttle": {"name": "Shuttle Kestrel", "kind": "vehicle"},
    }
    errors = semantic_output_errors("director_establish", _establish(entities=inert))
    assert errors == [], errors


def test_an_unkinded_entity_does_not_fail_an_opening():
    """`kind` is a freeform model string. A missing one is not evidence of an
    agent, and this error is fatal -- so silence means exempt."""
    errors = semantic_output_errors("director_establish", _establish(
        entities={"thing": {"name": "Something"}},
    ))
    assert errors == []


def test_the_shipped_example_satisfies_its_own_rule():
    from schemas import output_example
    ex = output_example("director_establish")
    assert not any("absent from positions" in e for e in
                   semantic_output_errors("director_establish", ex))


# --- an opening can express a hold ----------------------------------------

def test_establish_carries_contact_ops_through_validation():
    """Declared on DirectorEstablish so the round-trip keeps it -- an
    undeclared field validates cleanly and is then silently dropped, which is
    how `stations` stayed dead in 45 consecutive scenes."""
    out, _warnings = validate_llm_output("director_establish", _establish(
        contact_ops=[{"op": "add", "actor": "Ada", "actor_part": "hand",
                      "target": "Bo", "target_part": "wrist",
                      "manner": "gripping"}],
    ))
    assert out["contact_ops"] == [
        {"op": "add", "actor": "Ada", "actor_part": "hand",
         "target": "Bo", "target_part": "wrist", "manner": "gripping"}
    ]


def test_establish_defaults_contact_ops_to_empty():
    out, _warnings = validate_llm_output("director_establish", _establish())
    assert out["contact_ops"] == []


def test_the_establish_tail_routes_contact_ops_into_the_state_diff():
    """The tail is what makes the field reach spatial.apply_contact_ops: the
    merge reads state_diff.contact_ops, never the top-level key."""
    import inspect
    import agents.director as director
    src = inspect.getsource(director.director_establish)
    assert '"contact_ops"' in src, \
        "director_establish's state_diff tail must carry contact_ops"


def test_a_declared_hold_reaches_scene_contacts_through_the_ordinary_merge():
    from spatial import merge_scene_with_diff
    scene = merge_scene_with_diff({}, {
        "rooms": {"alley": {"name": "Alley", "desc": "Wet brick.",
                            "adjacent": []}},
        "positions": {"Ada": "alley", "Bo": "alley"},
        "contact_ops": [{"op": "add", "actor": "Ada", "actor_part": "hand",
                         "target": "Bo", "target_part": "wrist",
                         "manner": "gripping"}],
    })
    contacts = scene.get("contacts") or []
    assert contacts, "an opening's declared hold must survive the merge"
    assert any(c.get("actor") == "Ada" and c.get("target") == "Bo"
               for c in contacts), contacts


# --- arriving inside something is not climbing into it --------------------

def _enclosed_scene(positions, contained=None):
    return {
        "rooms": {
            "hold": {"name": "Hold", "desc": "Inside the wagon.",
                     "parent_entity": "wagon", "adjacent": []},
            "road": {"name": "Road", "desc": "Outside.", "adjacent": []},
        },
        "entities": {"wagon": {"name": "Wagon", "kind": "vehicle",
                               "container": True, "interior_rooms": ["hold"]}},
        "positions": dict(positions),
        "contained": dict(contained or {}),
    }


def test_the_opening_turn_invents_no_crossing_for_a_body_already_inside():
    """prev_scene is empty on turn 0, so every enclosed body used to read
    was_hidden=False -> now_hidden=True and was recorded mid-entry. Live, that
    gave BOTH occupants of a vehicle a {from: X, to: X} crossing -- including
    the one whose vehicle it was, who had not moved at all."""
    new = _enclosed_scene({"Ada": "hold", "Bo": "hold", "wagon": "road"})
    infer_threshold_crossings(None, None, {}, new, ["Ada", "Bo"])
    assert crossing_of(new, "Ada") is None
    assert crossing_of(new, "Bo") is None
    assert not new.get("crossings")


def test_a_body_joining_the_cast_already_enclosed_records_no_crossing():
    """Same rule mid-story: nobody watched them go in, because they were not
    there to be watched."""
    prev = _enclosed_scene({"Ada": "hold", "wagon": "road"})
    new = _enclosed_scene({"Ada": "hold", "Bo": "hold", "wagon": "road"})
    infer_threshold_crossings(None, None, prev, new, ["Ada", "Bo"])
    assert crossing_of(new, "Bo") is None


def test_a_body_that_really_climbs_in_is_still_recorded():
    """The guard must not cost the case the branch exists for: a body that WAS
    in the scene, unhidden, and is now inside something."""
    prev = _enclosed_scene({"Ada": "road", "wagon": "road"})
    new = _enclosed_scene(
        {"Ada": "road", "wagon": "road"},
        contained={"Ada": {"in": "wagon", "mode": "stowed"}},
    )
    infer_threshold_crossings(None, None, prev, new, ["Ada"])
    assert crossing_of(new, "Ada") == {
        "from": "road", "to": "road", "beats": THRESHOLD_CROSSING_BEATS}


def test_a_body_that_climbs_back_out_is_still_recorded():
    prev = _enclosed_scene(
        {"Ada": "road", "wagon": "road"},
        contained={"Ada": {"in": "wagon", "mode": "stowed"}},
    )
    new = _enclosed_scene({"Ada": "road", "wagon": "road"})
    infer_threshold_crossings(None, None, prev, new, ["Ada"])
    assert crossing_of(new, "Ada") == {
        "from": "road", "to": "road", "beats": THRESHOLD_CROSSING_BEATS}
