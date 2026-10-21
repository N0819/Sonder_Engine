"""VOICES CARRY UNLESS SOMETHING IN THE STORY STOPS THEM (the owner,
2026-10-20; `spatial_senses.hear_level`, `DESIGN_SOUND_FIELD.md` § 11).

"The sound system repeatedly wars with both reality and fiction" -- after a
kettle the opening of chat 176 wrote `loud` (read as 80 dB at a pace) turned
even a shout three paces off into "Thank...", a shut door a pace away ate a
question (chat 177 turn 21), and rain broke dialogue into "...word...
word..." until 2026-09-26. The verdict had been signal against noise on the
cell grid. It is now a table over what stands between two bodies, each entry
the answer a decibel budget from real hearing gives with margin, with noise
entering only from what the story makes deafening.

The rules, one test (or more) each:

  1. one room, or through an opening: a voiced line is whole; breath is
     private beyond reach -- whole within it, a mutter in pieces a pace or
     two off, gone beyond; under the open sky a voice falls with distance,
     well past a street's width;
  2. a shut door: whole at its two faces, muffled from farther off, a raised
     voice and a shout whole, breath gone; a heavy door keeps its stronger
     loss;
  3. a wall passes a shout as a murmur (pinned where it always was:
     `test_sound_field.test_the_room_graph_only_answers_where_the_edge_model_
     cannot`, `test_spatial`'s wall rows);
  4. noise masks speech only from what the story makes deafening, or an
     event it says drowns everything out, and only within its reach -- with
     a seen face worth several decibels there;
  5. big sounds keep their reach (`test_sound_field`'s far-field rows and
     `test_distant_sound_delivery`, unchanged);
  6. the firewall's refusals stand: a whisper across a room, a voice behind
     a far shut door, a normal voice from another building.

Every scene is a story's shape; every rule is the class.
"""

from __future__ import annotations

import copy

from world.spatial import (hear_level, hearing_reason, normalize_sensory_event,
                           sound_field, spatial_rel_between)

VOLUMES = ("whisper", "mutter", "normal", "loud", "shout")


def _heard(sc, listener, speaker, **kwargs):
    rel = spatial_rel_between(sc, listener, speaker, **kwargs)
    return {v: hear_level(rel, v) for v in VOLUMES}, rel


# ---------------------------------------------------------------------------
# The kitchen: chat 176 turn 2
# ---------------------------------------------------------------------------

def _kitchen(*, kettle="loud", hinami=(2, 4), mellisande=(2, 1), rain=True):
    """Chat 176's kitchen at turn 2, as its checkpoint holds it: five paces
    square, furnished, a table in the middle, a kettle whistling on the
    range that the opening wrote `loud`, rain on the roof. Hinami just inside
    the front door, Mellisande at the table three paces off."""
    kitchen = {
        "name": "The Kitchen", "exposure": "enclosed", "surface": "furnished",
        "extent": {"w": 5, "d": 5}, "light": "lit",
        "anchors": {
            "kitchen_table": {"desc": "A scarred deal table", "height": "waist",
                              "footprint": "large", "cell": [2, 2],
                              "extent": {"w": 2, "d": 2}},
            "kitchen_range": {"desc": "the range", "dir": "n", "height": "waist",
                              "footprint": "small", "cell": [3, 0]}},
        "adjacent": [{"to": "path", "barrier": "closed_door", "material": "wood",
                      "dir": "s", "offset": 0.5}],
    }
    path = {"name": "The Path", "exposure": "open", "extent": {"w": 3, "d": 12},
            "anchors": {},
            "adjacent": [{"to": "kitchen", "barrier": "closed_door",
                          "material": "wood", "dir": "n", "offset": 0.5}]}
    sc = {
        "rooms": {"kitchen": kitchen, "path": path},
        "positions": {"Hinami": "kitchen", "Mellisande": "kitchen",
                      "the kettle": "kitchen"},
        "stations": {"Hinami": {"at": None, "near": [], "cell": list(hinami)},
                     "Mellisande": {"at": None, "near": [],
                                    "cell": list(mellisande)},
                     "the kettle": {"at": "kitchen_range"}},
        "entities": {"the kettle": {
            "name": "the kettle", "kind": "object", "portable": True,
            "description": "A squat tin kettle with steam jetting from its spout.",
            "state": {"whistling": True}, "sound_source": kettle}},
        "poses": {}, "orientation": {}, "contained": {},
    }
    if rain:
        sc["weather"] = {"precipitation": "rain", "precipitation_kind": "liquid",
                         "intensity": "moderate", "wind": "breeze",
                         "sky": "overcast", "cloud": "covered"}
    return sc


def test_a_kettle_takes_nothing_from_a_shout_three_paces_off():
    """Chat 176 turn 2: "Thank..." -- a shout three paces off across a
    kitchen arrived in pieces under a kettle written `loud`. A kettle is an
    everyday thing; a voice in one room is heard whole."""
    heard, rel = _heard(_kitchen(), "Mellisande", "Hinami")
    assert {v: heard[v] for v in ("normal", "loud", "shout")} == {
        "normal": "full", "loud": "full", "shout": "full"}
    assert "masking_db" not in rel
    # ...and it is the same with the kettle quiet: the kettle was never it.
    quiet, _ = _heard(_kitchen(kettle=None), "Mellisande", "Hinami")
    assert quiet == heard


def test_a_whisper_within_reach_is_whole_whatever_runs_beside_it():
    """A whisper is speech made for the ear beside it, and the kettle on the
    range a pace off does not take it."""
    sc = _kitchen(hinami=(2, 4), mellisande=(2, 3))
    heard, rel = _heard(sc, "Mellisande", "Hinami")
    assert rel.get("reach") == "within_reach"
    assert heard["whisper"] == "full" and heard["mutter"] == "full"


def test_breath_is_private_beyond_reach():
    """Whole within reach; a mutter in pieces a pace or two off, where its
    voice still leads the room's own ring; a whisper gone there, and both
    gone across the room. TIGHTER than the rule it replaces for a whisper a
    pace or two off, which was caught in pieces: the owner's "private
    beyond arm's reach"."""
    same = {"same_room": True, "barrier": "open"}
    for tier, whisper, mutter in (("within_reach", "full", "full"),
                                  ("near", "none", "fragment"),
                                  ("across", "none", "none"),
                                  (None, "full", "full")):
        assert hear_level(same, "whisper", proximity=tier) == whisper, tier
        assert hear_level(same, "mutter", proximity=tier) == mutter, tier
    # Where the field places both bodies, the paces between them decide:
    # three across the kitchen is past a whisper's two and inside a
    # mutter's three -- the distances a still room gave them before.
    heard, rel = _heard(_kitchen(), "Mellisande", "Hinami")
    assert rel.get("paces") == 3.0
    assert heard["whisper"] == "none" and heard["mutter"] == "full"
    # Four paces off a mutter is in pieces, five gone; noise has no say.
    hall = _klaxon_hall(klaxon=None, speaker=(0, 3), listener=(4, 3))
    heard, rel = _heard(hall, "B", "A")
    assert rel.get("paces") == 4.0 and heard["mutter"] == "fragment"
    hall = _klaxon_hall(klaxon=None, speaker=(0, 3), listener=(5, 3))
    assert _heard(hall, "B", "A")[0]["mutter"] == "none"


# ---------------------------------------------------------------------------
# Under the sky
# ---------------------------------------------------------------------------

def _street(paces, *, weather=None, exposure="open"):
    """A street under the sky, two bodies `paces` apart along it."""
    sc = {"rooms": {"street": {"name": "the street", "exposure": exposure,
                               "extent": {"w": 96, "d": 6}, "anchors": {},
                               "adjacent": []}},
          "positions": {"A": "street", "B": "street"},
          "stations": {"A": {"cell": [1, 3]}, "B": {"cell": [1 + paces, 3]}},
          "entities": {}, "poses": {}, "orientation": {}, "contained": {}}
    if weather:
        sc["weather"] = weather
    return sc


DOWNPOUR = {"precipitation": "rain", "precipitation_kind": "liquid",
            "intensity": "heavy", "wind": "gale", "sky": "storm",
            "cloud": "covered"}


def test_a_call_carries_across_a_street_in_heavy_rain():
    """The owner, 2026-09-26: "you could still call to someone across a
    street in rain and not really strain your voice." Sixteen paces -- a
    twelve-metre street -- in a downpour with a gale: an ordinary voice and
    a call are whole. Weather never masks speech."""
    heard, _rel = _heard(_street(16, weather=DOWNPOUR), "B", "A")
    assert heard["normal"] == "full" and heard["loud"] == "full"
    assert heard["whisper"] == "none"


def test_under_the_sky_a_voice_falls_away_with_distance():
    """No ceiling gives a voice back outdoors: it falls 6 dB a doubling, so
    an ordinary voice is whole to forty-five paces over an open place's
    quiet floor -- nearly three times a street -- and in pieces beyond; a
    raised one carries to a hundred and forty."""
    near, rel = _heard(_street(40), "B", "A")
    assert rel.get("open_air_loss_db") is not None
    assert near["normal"] == "full"
    far, _ = _heard(_street(90), "B", "A")
    assert far["normal"] == "fragment" and far["loud"] == "full"
    # Indoors the same length is a hall, and its ring holds a voice up.
    hall, rel = _heard(_street(90, exposure="enclosed"), "B", "A")
    assert "open_air_loss_db" not in rel and hall["normal"] == "full"


def test_an_unplaced_body_under_the_sky_is_not_taken_by_a_guess():
    """A body with no station stands at the room's centre on the field --
    a guess -- and a guess must not take a voice away."""
    sc = _street(90)
    sc["stations"].pop("B")
    heard, rel = _heard(sc, "B", "A")
    assert "open_air_loss_db" not in rel and heard["normal"] == "full"


# ---------------------------------------------------------------------------
# A shut door: chat 177 turn 21
# ---------------------------------------------------------------------------

def _upstairs(*, material="wood", speaker_cell=(0, 0), listener_cell=(1, 1),
              landing=(2, 2)):
    """Chat 177's upper storey: a two-by-two landing and a three-by-two
    second room, one plank door between them, heavy rain on the roof. A
    larger `landing` gives the speaker somewhere to stand away from the
    door: on the live two-by-two every cell is at it."""
    door = {"barrier": "closed_door", "material": material, "offset": 1.0}
    return {
        "rooms": {
            "landing": {"name": "The Landing", "exposure": "enclosed",
                        "size": "tiny", "extent": {"w": landing[0], "d": landing[1]},
                        "anchors": {}, "adjacent": [{"to": "spare", "dir": "w", **door}]},
            "spare": {"name": "The Second Room", "exposure": "enclosed",
                      "size": "tiny", "extent": {"w": 3, "d": 2},
                      "anchors": {}, "adjacent": [{"to": "landing", "dir": "e", **door}]}},
        "positions": {"Hinami": "landing", "Mellisande": "spare"},
        "stations": {"Hinami": {"at": None, "near": [], "cell": list(speaker_cell)},
                     "Mellisande": {"at": None, "near": [], "cell": list(listener_cell)}},
        "weather": {"precipitation": "rain", "precipitation_kind": "liquid",
                    "intensity": "heavy", "wind": "breeze", "sky": "overcast",
                    "cloud": "covered"},
        "entities": {}, "poses": {}, "orientation": {}, "contained": {},
    }


def test_a_shut_door_muffles_from_farther_off_and_carries_a_raised_voice():
    """A normal voice spoken at a shut door is whole beyond it -- at its
    other face, or two paces into the small room behind it, which is chat
    177 turn 21 as its checkpoint holds it ("What was that?") -- and the
    answer comes back the same way. With nobody at the door it is muffled,
    in pieces; a raised voice and a shout carry through whole; breath stays
    this side of it."""
    at_door, rel = _heard(_upstairs(), "Mellisande", "Hinami")
    assert rel.get("door_reach") is True and at_door["normal"] == "full"
    stepped_back, rel = _heard(_upstairs(listener_cell=(0, 0)),
                               "Mellisande", "Hinami")
    assert rel.get("door_reach") is True and stepped_back["normal"] == "full"
    answer, _rel = _heard(_upstairs(listener_cell=(0, 0)), "Hinami", "Mellisande")
    assert answer["normal"] == "full"
    far, rel = _heard(_upstairs(landing=(5, 4), speaker_cell=(4, 3),
                                listener_cell=(0, 0)), "Mellisande", "Hinami")
    assert "door_reach" not in rel
    assert far == {"whisper": "none", "mutter": "none", "normal": "fragment",
                   "loud": "full", "shout": "full"}
    assert hearing_reason(rel, "normal") == "shut_door_from_farther_off"
    assert hearing_reason(rel, "whisper") == "breath_through_a_door"


def test_a_heavy_door_keeps_its_stronger_loss():
    """Iron shifts a door one rung more solid, and it stays a rung past a
    light door everywhere. With a body at it a normal voice comes through
    muffled and a raised one whole -- what a light door gives with nobody
    at it, where a light door with a body at it passes a normal voice
    whole; with nobody at it a normal voice is gone and a raised one and a
    shout cross as their low half. Breath never."""
    heard, rel = _heard(_upstairs(material="iron"), "Mellisande", "Hinami")
    assert "door_reach" not in rel and rel.get("reach") == "within_reach"
    assert heard == {"whisper": "none", "mutter": "none", "normal": "fragment",
                     "loud": "full", "shout": "full"}
    heard, rel = _heard(_upstairs(material="iron", landing=(5, 4),
                                  speaker_cell=(4, 3), listener_cell=(0, 0)),
                        "Mellisande", "Hinami")
    assert heard == {"whisper": "none", "mutter": "none", "normal": "none",
                     "loud": "fragment", "shout": "fragment"}
    assert hearing_reason(rel, "normal") == "heavy_door_or_glass"


# ---------------------------------------------------------------------------
# What may mask: a deafening source, an event that drowns everything
# ---------------------------------------------------------------------------

def _klaxon_hall(*, klaxon="deafening", speaker=(1, 3), listener=(2, 3)):
    """A medium hall with a klaxon on its north wall; the two bodies pinned."""
    return {
        "rooms": {"hall": {"name": "the hall", "exposure": "enclosed",
                           "extent": {"w": 8, "d": 6}, "anchors": {
                               "horn": {"desc": "the klaxon", "dir": "n",
                                        "cell": [4, 0]}},
                           "adjacent": [{"to": "yard", "barrier": "closed_door",
                                         "dir": "s", "offset": 0.5}]},
                  "yard": {"name": "the yard", "exposure": "open",
                           "extent": {"w": 12, "d": 12}, "anchors": {},
                           "adjacent": [{"to": "hall", "barrier": "closed_door",
                                         "dir": "n", "offset": 0.5}]}},
        "positions": {"A": "hall", "B": "hall", "klaxon": "hall"},
        "stations": {"A": {"cell": list(speaker)}, "B": {"cell": list(listener)},
                     "klaxon": {"at": "horn"}},
        "entities": {"klaxon": {"name": "the klaxon", "kind": "machine",
                                "sound_source": klaxon}},
        "poses": {}, "orientation": {}, "contained": {},
    }


def test_only_a_deafening_source_masks():
    """A `loud` horn is everyday noise and takes nothing; a `deafening` one
    is noise no voice is raised over: at arm's length a line is caught in
    pieces, across the hall it is lost, and breath is lost everywhere."""
    loud, rel = _heard(_klaxon_hall(klaxon="loud"), "B", "A")
    assert "masking_db" not in rel and loud["normal"] == "full"
    beside, rel = _heard(_klaxon_hall(), "B", "A")
    assert rel.get("masking_db") is not None
    assert beside["normal"] == "fragment" and beside["shout"] == "fragment"
    assert beside["whisper"] == "none"
    assert hearing_reason(rel, "normal") == "deafening"
    across, rel = _heard(_klaxon_hall(speaker=(0, 5), listener=(7, 1)), "B", "A")
    assert across["normal"] == "none" and across["shout"] == "none"


def test_a_deafening_source_masks_only_within_its_reach():
    """Outside the hall's shut door, in the yard, the klaxon is a noise
    through a door: two people talking there are not drowned by it."""
    sc = _klaxon_hall()
    sc["positions"].update({"A": "yard", "B": "yard"})
    sc["stations"].update({"A": {"cell": [6, 9]}, "B": {"cell": [7, 9]}})
    heard, rel = _heard(sc, "B", "A")
    assert heard["normal"] == "full", rel.get("masking_db")


def test_a_face_seen_in_the_din_is_followed_further():
    """Seeing the speaker's face is worth several decibels where noise is
    what decides: across the klaxon hall, an unseen speaker is lost and a
    watched one is caught in pieces."""
    _heard_, rel = _heard(_klaxon_hall(speaker=(0, 5), listener=(7, 1)), "B", "A")
    assert hear_level(rel, "shout") == "none"
    assert hear_level(rel, "shout", seen=True) == "fragment"


def test_an_event_the_story_says_drowns_everything_masks_its_beat():
    """A one-beat sound is a moment and masks nothing (the owner,
    2026-09-25) -- unless the story says it drowns everything out, for as
    long as it lasts. The flag survives the event's normaliser and nothing
    else is read off it."""
    kept = normalize_sensory_event({"room": "hall", "level": "loud",
                                    "detail": "the rotor wash", "drowns": True},
                                   {"hall": {}})
    assert kept["drowns"] is True
    assert "drowns" not in normalize_sensory_event(
        {"room": "hall", "level": "loud", "drowns": "yes"}, {"hall": {}})
    sc = _klaxon_hall(klaxon=None)
    roar = [{"kind": "sound", "room": "hall", "level": "loud",
             "detail": "the rotor wash", "drowns": True}]
    field = sound_field(sc, "B", events=roar)
    heard, rel = _heard(sc, "B", "A", sound=field)
    assert rel.get("masking_db") is not None
    assert heard["normal"] != "full"
    moment = [dict(roar[0], drowns=False)]
    heard, rel = _heard(sc, "B", "A", sound=sound_field(sc, "B", events=moment))
    assert "masking_db" not in rel and heard["normal"] == "full"


# ---------------------------------------------------------------------------
# Rooms away, and another building
# ---------------------------------------------------------------------------

def _run(hops, barrier="open_door", fire=False, last=None):
    """`hops` rooms in a line joined by `barrier`, the last edge by `last`."""
    rooms = {}
    for i in range(hops + 1):
        adjacent = []
        if i:
            kind = last if (last and i == hops) else barrier
            adjacent.append({"to": "r%d" % (i - 1), "barrier": kind, "dir": "w",
                             **({"material": "iron"} if kind == "iron_door" else {})})
        if i < hops:
            kind = last if (last and i + 1 == hops) else barrier
            adjacent.append({"to": "r%d" % (i + 1), "barrier": kind, "dir": "e",
                             **({"material": "iron"} if kind == "iron_door" else {})})
        for edge in adjacent:
            if edge["barrier"] == "iron_door":
                edge["barrier"] = "closed_door"
        rooms["r%d" % i] = {"name": "room %d" % i, "exposure": "enclosed",
                            "size": "medium", "anchors": {}, "adjacent": adjacent}
    sc = {"rooms": rooms, "positions": {"L": "r0", "S": "r%d" % hops},
          "stations": {}, "entities": {}, "poses": {}, "orientation": {},
          "contained": {}}
    if fire:
        sc["entities"]["fire"] = {"name": "the fire", "sound_source": "audible"}
        sc["positions"]["fire"] = "r0"
    return sc


def test_a_voice_rooms_away_is_graded_against_the_quiet_floor():
    """Two rooms down an open run, a fire crackling beside the listener: the
    voice is graded by the room graph's loss against the listening room's
    QUIET floor -- the place's own level, never what runs in it."""
    quiet, rel = _heard(_run(2), "L", "S")
    assert rel.get("far_loss_db") is not None and quiet["normal"] == "full"
    by_the_fire, _ = _heard(_run(2, fire=True), "L", "S")
    assert by_the_fire == quiet


def test_a_body_in_another_building_hears_nothing_of_a_normal_voice():
    """Two houses across a street, each parlour open on its hall and each
    front door shut on the street: a normal voice in one parlour does not
    reach the other's, and a shout crosses as pieces at most.

    (With BOTH front doors standing open as well, the far field's room
    lengths put a normal voice into the other parlour in pieces -- measured
    42.6 dB of loss -- because it charged nothing for a voice leaving a
    room. Since 2026-10-20 each of the four openings pays the table's
    coupling (DESIGN_SOUND_FIELD.md § 20): 57.0 dB, the voice and no word.
    The open street is still charged as a room's length: registered in
    `docs/UNBUILT_PERCEPTION.md` § 1.159.)"""
    def room_(name, exposure, adjacent, w=6, d=6):
        return {"name": name, "exposure": exposure, "extent": {"w": w, "d": d},
                "anchors": {}, "adjacent": adjacent}
    rooms = {
        "parlour_a": room_("parlour A", "enclosed",
                           [{"to": "hall_a", "barrier": "open_door", "dir": "s"}]),
        "hall_a": room_("hall A", "enclosed",
                        [{"to": "parlour_a", "barrier": "open_door", "dir": "n"},
                         {"to": "street", "barrier": "closed_door", "dir": "s"}]),
        "street": room_("the street", "open",
                        [{"to": "hall_a", "barrier": "closed_door", "dir": "n"},
                         {"to": "hall_b", "barrier": "closed_door", "dir": "s"}],
                        w=30, d=16),
        "hall_b": room_("hall B", "enclosed",
                        [{"to": "street", "barrier": "closed_door", "dir": "n"},
                         {"to": "parlour_b", "barrier": "open_door", "dir": "s"}]),
        "parlour_b": room_("parlour B", "enclosed",
                           [{"to": "hall_b", "barrier": "open_door", "dir": "n"}]),
    }
    sc = {"rooms": rooms, "positions": {"S": "parlour_a", "L": "parlour_b"},
          "stations": {}, "entities": {}, "poses": {}, "orientation": {},
          "contained": {}}
    heard, rel = _heard(sc, "L", "S")
    assert heard["normal"] == "none", rel.get("far_loss_db")
    assert heard["shout"] in ("none", "fragment")


def test_a_far_way_through_a_heavy_door_is_muffled():
    """Rooms away, a voice that crossed a heavy door on the way arrives as
    its low half -- in pieces at best, however little the rest of the way
    costs -- as it does through the same door next door. A shut ordinary
    door does not do that to a shout: one carries a shout whole next door
    and two rooms on."""
    light, rel = _heard(_run(2, last="closed_door"), "L", "S")
    assert rel.get("far_muffled") is False and light["shout"] == "full"
    heavy, rel = _heard(_run(2, last="iron_door"), "L", "S")
    assert rel.get("far_muffled") is True
    assert heavy["shout"] == "fragment" and heavy["normal"] == "none"
    assert hearing_reason(rel, "shout") == "rooms_away_muffled"


# ---------------------------------------------------------------------------
# The rule's own words
# ---------------------------------------------------------------------------

def test_the_reason_names_the_clause_that_decided():
    same = {"same_room": True, "barrier": "open"}
    assert hearing_reason(same, "normal") == ""
    assert hearing_reason(same, "whisper", proximity="across") == "breath_beyond_reach"
    assert hearing_reason({"barrier": "wall"}, "normal") == "wall"
    assert hearing_reason({"barrier": "unknown", "distance": "remote"},
                          "normal") == "no_air"
    assert hearing_reason({"same_room": True, "source_enclosed": True},
                          "normal") == "conducted"


def test_a_pitched_line_is_the_quietest_voice_that_reaches_its_addressee():
    """Within reach a whisper; three paces off a mutter; across a room an
    ordinary voice; through a shut door from farther off a raised one --
    and nobody beyond the addressee is reached by more than that."""
    from world.spatial import pitched_level_db, word_for_level
    beside = _kitchen(hinami=(2, 4), mellisande=(2, 3))
    assert word_for_level(pitched_level_db(beside, "Hinami", "Mellisande")) == "whisper"
    three = _kitchen()
    assert word_for_level(pitched_level_db(three, "Hinami", "Mellisande")) == "mutter"
    hall = _klaxon_hall(klaxon=None, speaker=(0, 5), listener=(7, 1))
    assert word_for_level(pitched_level_db(hall, "A", "B")) == "normal"
    door = _upstairs(landing=(5, 4), speaker_cell=(4, 3), listener_cell=(0, 0))
    assert word_for_level(pitched_level_db(door, "Hinami", "Mellisande")) == "loud"


def test_a_round_hears_a_whisper_as_perception_does(temp_db):
    """The interaction loop's own delivery reads the MEASURED reach tier, as
    every perception pass does. It read `proximity_rel`, whose `near` is
    also its answer for two bodies nobody stationed, so under the hearing
    rule a whisper between unstationed bodies would be refused in the round
    and delivered whole by perception's passes. Stationed across the room,
    it is refused in both."""
    from agents.loops import deterministic_micro_perception
    from tests.test_a_pitched_line_is_solved_for_its_listener import _micro_ctx
    ctx, ids = _micro_ctx(temp_db)
    words = "Not here. Wait for me by the stair."

    def delivered(sc):
        result = {"sequence": [{
            "type": "speech", "text": words, "volume": "whisper",
            "tone": "", "visibility": "overt", "conceal_from": [],
            "targets": ["Matron"],
            "event_id": f"turn:{ctx.turn.id}:character:{ids['Clara']}:0:speech",
        }]}
        views, _ = deterministic_micro_perception(ctx, ids["Clara"], result, sc)
        return " ".join(views.get(ids["Matron"]) or [])

    room = {"name": "ballroom", "extent": {"w": 12, "d": 8}, "anchors": {
        "far_wall": {"desc": "the far wall", "dir": "w"},
        "near_wall": {"desc": "the near wall", "dir": "e"}}, "adjacent": []}
    unstationed = {"location": "ballroom", "time": "night",
                   "rooms": {"ballroom": room},
                   "positions": {"Clara": "ballroom", "Matron": "ballroom",
                                 "Crane": "ballroom"},
                   "stations": {}, "entities": {}, "attire": {}, "overlays": {}}
    assert words in delivered(unstationed)
    across = copy.deepcopy(unstationed)
    across["stations"] = {"Clara": {"at": "near_wall", "near": []},
                          "Matron": {"at": "far_wall", "near": []}}
    assert words not in delivered(across)
