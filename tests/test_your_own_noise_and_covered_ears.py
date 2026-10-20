"""YOUR OWN NOISE, AND COVERED EARS (DESIGN_SOUND_FIELD.md § 13, wave B1,
2026-10-20).

Real world: you hear others less while you are making noise yourself -- a
drill, a hair-dryer, a vacuum cleaner in your own hands -- and hands over
the ears take about 15-25 dB from what reaches them, a finger or a plug in
the canal 25-30. The hearing rule priced the PATH between two bodies and
nothing at the end of it, so a body with its hands clamped over its ears
followed a conversation in the next room word for word, and one running a
drill heard a line said to it from across the workshop as if the room were
silent.

The class, read from TYPED state only:

  1. a settled contact over BOTH of the listener's ears covers them (on
     the surface) or stops them (in the canal); one ear, a moving hand, or
     somebody else's ears change nothing;
  2. a covered ear takes what it takes from everything: whispers and the
     next room's talk go, a voice in the room stays;
  3. a running thing in the listener's own hands, loud enough to be a din
     at their ear, is noise the speaker does not share -- it caps what they
     follow, addressee or not; a bystander beside them is not capped by a
     machine they do not hold;
  4. `hearing_reason` says which;
  5. a sound, not only a line: a covered ear misses a faint sound in the
     next room that an open one catches.
"""

from __future__ import annotations

from world.spatial import (EARS_COVERED_DB, EARS_STOPPED_DB, ear_cover_db,
                           hear_level, hearing_reason, heard_events,
                           own_noise_db, sound_field, spatial_rel_between,
                           voice_carries)

VOLUMES = ("whisper", "mutter", "normal", "loud", "shout")


def _scene(cells, *, contacts=(), held_drill=False, back_room=None):
    rooms = {"shop": {"name": "the workshop", "exposure": "enclosed",
                      "extent": {"w": 10, "d": 8}, "anchors": {},
                      "adjacent": []}}
    positions = {k: "shop" for k in cells}
    stations = {k: {"cell": list(v)} for k, v in cells.items()}
    if back_room:
        rooms["shop"]["adjacent"] = [{"to": "back", "barrier": "open",
                                      "bearing": "e"}]
        rooms["back"] = {"name": "the back room", "exposure": "enclosed",
                         "extent": {"w": 6, "d": 6}, "anchors": {},
                         "adjacent": [{"to": "shop", "barrier": "open",
                                       "bearing": "w"}]}
        for who, cell in back_room.items():
            positions[who] = "back"
            stations[who] = {"cell": list(cell)}
    sc = {"rooms": rooms, "positions": positions, "stations": stations,
          "entities": {}, "poses": {}, "orientation": {}, "contained": {},
          "contacts": list(contacts)}
    if held_drill:
        sc["entities"]["drill"] = {"name": "a drill", "kind": "object",
                                   "sound_source": "loud",
                                   "state": {"running": True},
                                   "held_by": "C"}
        sc["contained"]["drill"] = {"in": "C", "mode": "held"}
        sc["positions"]["drill"] = positions["C"]
    return sc


def _hands(who="C", part="ears", relation="surface", motion="settled",
           actor=None):
    return {"actor": actor or who, "actor_part": "hands", "target": who,
            "target_part": part, "manner": "press", "relation": relation,
            "motion": motion}


def _heard(sc, listener, speaker="A", addressed=True):
    rel = spatial_rel_between(sc, listener, speaker,
                              sound=sound_field(sc, listener))
    return rel, {v: hear_level(rel, v, addressed=addressed) for v in VOLUMES}


# --- 1. what covers the ears ------------------------------------------------

def test_hands_over_both_ears_cover_them_and_fingers_in_them_stop_them():
    cells = {"A": (1, 1), "C": (8, 6)}
    assert ear_cover_db(_scene(cells, contacts=[_hands()]), "C") == EARS_COVERED_DB
    assert ear_cover_db(_scene(cells, contacts=[_hands(relation="interior")]),
                        "C") == EARS_STOPPED_DB
    # A left and a right are both ears; the weaker covering is what passes.
    pair = [_hands(part="left ear"), _hands(part="right ear", relation="interior")]
    assert ear_cover_db(_scene(cells, contacts=pair), "C") == EARS_COVERED_DB
    # Another body's hands over C's ears cover them too.
    assert ear_cover_db(_scene(cells, contacts=[_hands(actor="A")]), "C") \
        == EARS_COVERED_DB


def test_one_ear_a_moving_hand_or_somebody_else_s_ears_cover_nothing():
    cells = {"A": (1, 1), "C": (8, 6)}
    for contacts in ([_hands(part="left ear")],          # one ear
                     [_hands(motion="moving")],          # rubbing, no seal
                     [_hands(who="A")],                  # A's ears, not C's
                     [_hands(part="shoulders")]):        # not an ear at all
        assert ear_cover_db(_scene(cells, contacts=contacts), "C") == 0.0


def test_the_corpus_ear_contacts_read_right():
    """Every ear contact in the owner's database, read as the rule reads it
    (chats 42-44, 50-51, 72-74, 178). Only one covers both ears: hands
    PRESSED over them (chat 44 turn 94). Lips at one ear, a thumb at an ear's
    base, fingertips CIRCLING the ears in a massage (a record from before
    `motion` existed, read the way the contact ledger reads one), and a thumb
    resting against the edge of a fox ear (chat 178 turn 25, written to the
    plural "fox ears") cover nothing."""
    cells = {"A": (1, 1), "C": (8, 6)}
    covers = {
        ("lips", "ear", "press", None, None): 0.0,
        ("lips", "ear", "brush", None, None): 0.0,
        ("thumb", "ear_base", "touch", None, None): 0.0,
        ("fingertips", "ears", "circle", None, None): 0.0,
        ("hands", "ears_and_hair", "massage", None, None): 0.0,
        ("hands", "ears", "press", None, None): EARS_COVERED_DB,
        ("thumb", "fox ears", "rest", "surface", "settled"): 0.0,
        ("mouth", "ear", "whisper", "surface", "settled"): 0.0,
    }
    for (actor_part, part, manner, relation, motion), want in covers.items():
        contact = {"actor": "A", "actor_part": actor_part, "target": "C",
                   "target_part": part, "manner": manner,
                   "relation": relation, "motion": motion}
        got = ear_cover_db(_scene(cells, contacts=[contact]), "C")
        assert got == want, (actor_part, part, manner, got)


# --- 2. a covered ear hears less -----------------------------------------------

def test_hands_over_the_ears_lose_the_next_room_and_keep_the_room():
    """Through an open doorway a normal voice arrives at about 42 dB: whole
    to an open ear, 22 through the palms -- muffled, in pieces. In the same
    room a voice still comes through the hands."""
    sc_open = _scene({"A": (1, 1)}, back_room={"C": (3, 3)})
    sc_covered = _scene({"A": (1, 1)}, back_room={"C": (3, 3)},
                        contacts=[_hands()])
    _rel, open_ear = _heard(sc_open, "C")
    rel, covered = _heard(sc_covered, "C")
    assert open_ear["normal"] == "full"
    assert covered["normal"] == "fragment"
    assert covered["loud"] == "full" and covered["shout"] == "full"
    assert hearing_reason(rel, "normal", addressed=True) == "ears_covered"
    # In the same room, a pace off: a voice through the hands is whole, a
    # whisper is gone.
    sc = _scene({"A": (1, 1), "C": (2, 1)}, contacts=[_hands()])
    _rel, near = _heard(sc, "C")
    assert near["normal"] == "full"
    assert near["whisper"] == "none"
    _rel, near_open = _heard(_scene({"A": (1, 1), "C": (2, 1)}), "C")
    assert near_open["whisper"] == "full"


# --- 3. your own noise --------------------------------------------------------

def test_a_drill_in_your_own_hands_caps_what_you_follow():
    """C runs a drill (`loud`, 68 dB at the hand): a normal line said TO
    them from across the workshop arrives in pieces, a shout whole. The same
    line to C without the drill is whole -- and the addressee rule of the
    din (noise never stops people talking to each other) does not save it,
    because this noise is at C's ear and not at the speaker's."""
    cells = {"A": (1, 1), "B": (2, 1), "C": (8, 6)}
    _rel, quiet = _heard(_scene(cells), "C")
    rel, drilling = _heard(_scene(cells, held_drill=True), "C")
    assert quiet["normal"] == "full"
    assert drilling["normal"] == "fragment"
    assert drilling["shout"] == "full"
    assert hearing_reason(rel, "normal", addressed=True) == "own_noise"
    # The voice itself still carries to the drilling ear.
    assert voice_carries(rel, "normal", addressed=True)
    assert own_noise_db(_scene(cells, held_drill=True), "C") is not None
    # B, beside the speaker, is not capped by a machine somebody else holds.
    _rel, beside = _heard(_scene(cells, held_drill=True), "B")
    assert beside["normal"] == "full" and beside["whisper"] == "full"
    assert own_noise_db(_scene(cells, held_drill=True), "B") is None
    # Only a din at the ear counts: a ticking watch in the hand is not
    # self-masking, and a whisper at arm's reach comes through it.
    near = {"A": (1, 1), "C": (2, 1)}
    watch = _scene(near, held_drill=True)
    watch["entities"]["drill"]["sound_source"] = "faint"
    assert own_noise_db(watch, "C") is None
    _rel, heard = _heard(watch, "C")
    assert heard["whisper"] == "full"
    # ...where the drill takes it.
    _rel, drilled = _heard(_scene(near, held_drill=True), "C")
    assert drilled["whisper"] == "none" and drilled["normal"] == "full"


# --- 5. a sound, not only a line ------------------------------------------------

def test_a_covered_ear_misses_a_faint_sound_in_the_next_room():
    event = {"kind": "sound", "source_room": "back", "room": "back",
             "level": "audible", "detail": "a chair scrapes"}
    sc_open = _scene({"C": (1, 1)}, back_room={"Z": (3, 3)})
    sc_covered = _scene({"C": (1, 1)}, back_room={"Z": (3, 3)},
                        contacts=[_hands()])
    assert heard_events(sc_open, "C", [event], room="shop")
    assert not heard_events(sc_covered, "C", [event], room="shop")
