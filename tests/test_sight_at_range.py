"""Distance is sight's second input: the text equivalent of a level of detail.

The owner, 2026-10-04: "for distant objects we might need something like
the text equivalent of an LOD", then "Go ahead" to: full detail to about
15 m (Wagenaar & van der Schrier 1996, the "rule of fifteen"), conduct --
posture, gait, what is worn, what a body does -- to about 100 m, shapes
beyond; size scales the bands; a known person keeps their name; the bands
hold indoors too (`world/spatial_range.py`).

Every scene here is LIT: the one far fixture the suite had before this (the
Moonlit Strand) is dim, and cannot tell a distance cap from a light cap.
One pace is 0.75 m, so 20 paces is 15 m and 133 paces is 100 m.
"""

from __future__ import annotations

import pytest

from world.spatial import (graded_sight, pair_range, sight_between,
                           visual_level_between)

RANK = {"none": 0, "shapes": 1, "conduct": 2, "full": 3}


def _square(w=96, d=96, **room):
    return {"rooms": {"square": {"name": "the square", "desc": ".",
                                 "exposure": "open", "extent": {"w": w, "d": d},
                                 "adjacent": [], **room}},
            "positions": {}, "stations": {}, "entities": {}}


def _put(sc, name, cell, room="square"):
    sc["positions"][name] = room
    sc["stations"][name] = {"cell": list(cell)}


# --------------------------------------------------------------------------
# The ladder
# --------------------------------------------------------------------------

def test_a_person_is_read_to_fifteen_metres_and_made_out_to_a_hundred():
    sc = _square()
    _put(sc, "Ada", (0, 0))
    for paces, want in ((19, "full"), (21, "conduct"), (95, "conduct")):
        _put(sc, "Ben", (paces, 0))
        assert visual_level_between(sc, "Ada", "Ben") == want, paces
    _put(sc, "Ben", (95, 95))                       # 100.8 m on the diagonal
    assert visual_level_between(sc, "Ada", "Ben") == "shapes"


def test_distance_only_ever_subtracts_and_never_blinds():
    """Past a hundred metres a person is a shape, never nothing; in the dim
    the distance takes only what the light left (the weaker of the two)."""
    cases = (((95, 95), None, "shapes"),      # 100.8 m, lit
             ((80, 0), "dim", "conduct"),      # 60 m, dim: the dim's conduct
             ((95, 95), "dim", "shapes"),      # 100.8 m, dim: the distance's shapes
             ((4, 0), "dim", "conduct"),       # 3 m, dim: the light alone
             ((4, 0), None, "full"))
    for cell, light, want in cases:
        sc = _square(**({"light": light} if light else {}))
        _put(sc, "Ada", (0, 0))
        _put(sc, "Ben", cell)
        grade = sight_between(sc, "Ada", "Ben")
        assert grade.range != "none", (cell, light)
        assert RANK[grade.level] <= RANK[grade.base], (cell, light)
        assert grade.level == want, (cell, light, grade)


def test_a_body_with_no_station_makes_no_claim():
    sc = _square()
    sc["positions"] = {"Ada": "square", "Ben": "square"}
    assert visual_level_between(sc, "Ada", "Ben") == "full"
    assert pair_range(sc, "Ada", "Ben").low is None


def test_bodies_at_one_long_anchor_are_never_dealt_apart_by_the_hash():
    """`body_cell` seats bodies at one anchor along it by hash -- "not a
    statement about any one of them". Six at one shoreline run were dealt
    seats tens of metres apart; none may lose the others' faces for it."""
    sc = _square(96, 10, anchors={"tideline": {"desc": "the tideline", "dir": "s",
                                               "footprint": "run", "height": "floor"}})
    for i in range(6):
        sc["positions"][f"B{i}"] = "square"
        sc["stations"][f"B{i}"] = {"at": "tideline"}
    assert {visual_level_between(sc, "B0", f"B{i}") for i in range(1, 6)} == {"full"}


def test_size_scales_the_bands():
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (53, 0))                        # 39.75 m
    assert visual_level_between(sc, "Ada", "Ben") == "conduct"
    sc["scales"] = {"Ben": 3.0}                     # a giant: a face to 45 m
    assert visual_level_between(sc, "Ada", "Ben") == "full"
    sc["scales"] = {"Ben": 0.5}
    _put(sc, "Ben", (12, 0))                        # 9 m: a half-size body's face is read to 7.5
    assert visual_level_between(sc, "Ada", "Ben") == "conduct"


# --------------------------------------------------------------------------
# Evidence: what is certain subtracts; a rise holds at the far end
# --------------------------------------------------------------------------

def _two_rooms(distance, size=5):
    def room(to, d):
        return {"name": to, "desc": ".", "extent": {"w": size, "d": size},
                "adjacent": [{"to": to, "barrier": "open", "dir": d,
                              "distance": distance}]}
    return {"rooms": {"a": room("b", "e"), "b": room("a", "w")},
            "positions": {"Ada": "a", "Ben": "b"}, "stations": {}, "entities": {}}


@pytest.mark.parametrize("distance,want", [
    ("far", "conduct"), ("50m", "conduct"), ("120m", "shapes"),
    ("200 m", "shapes"), ("remote", "shapes"), ("near", "full"), ("8m", "full")])
def test_an_authored_edge_is_read_as_its_distance(distance, want):
    """It used to cap at `shapes` flat for far and remote alike."""
    assert visual_level_between(_two_rooms(distance), "Ada", "Ben") == want


def test_a_rise_on_an_edge_holds_at_its_far_end():
    """A bare `far` is 20 to 75 m. A giant across it is not lifted to full on
    the 20 m floor: at 75 m, three times a person's face limit is 45 m."""
    sc = _two_rooms("far")
    sc["scales"] = {"Ben": 3.0}
    assert visual_level_between(sc, "Ada", "Ben") == "conduct"


def _gateway(ada, ben):
    sc = {"rooms": {
        "yard": {"name": "yard", "desc": ".", "exposure": "open", "extent": {"w": 40, "d": 10},
                 "adjacent": [{"to": "lane", "barrier": "open", "dir": "e", "width": 10}]},
        "lane": {"name": "lane", "desc": ".", "exposure": "open", "extent": {"w": 60, "d": 10},
                 "adjacent": [{"to": "yard", "barrier": "open", "dir": "w", "width": 10}]}},
        "positions": {"Ada": "yard", "Ben": "lane"}, "stations": {}, "entities": {}}
    sc["stations"]["Ada"] = ada
    sc["stations"]["Ben"] = ben
    return sc


def test_a_measured_clear_line_answers_what_the_cone_guessed():
    """Two pinned bodies four paces apart across the gateway between two big
    open rooms graded `shapes` -- the doorway cone's guess for placement
    unknown. Their placement is known; the distance answers."""
    sc = _gateway({"cell": [38, 5]}, {"cell": [1, 5]})
    assert visual_level_between(sc, "Ada", "Ben") == "full"
    sc = _gateway({"cell": [38, 5]}, {"cell": [59, 5]})       # 46.5 m
    assert visual_level_between(sc, "Ada", "Ben") == "conduct"


def test_a_dealt_seat_is_no_measurement_and_keeps_the_cone():
    """A body merely `at` an anchor sits on a hash-dealt seat: the cone that
    answers for placement unknown still answers for it."""
    sc = _gateway({"cell": [38, 5]}, {"at": "post"})
    sc["rooms"]["lane"]["anchors"] = {"post": {"desc": "a post", "dir": "w"}}
    grade = sight_between(sc, "Ada", "Ben")
    assert not grade.evidence.exact
    assert grade.level != "full"


# --------------------------------------------------------------------------
# The observer's eyes carry the bands; they never lift past them
# --------------------------------------------------------------------------

def test_keen_eyes_read_further_and_dull_ones_never_lose_the_body():
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (30, 0))                        # 22.5 m
    keen = [{"channel": "sight", "acuity": "keen"}]
    assert graded_sight(sc, "Ada", "Ben") == "conduct"
    assert graded_sight(sc, "Ada", "Ben", keen) == "full"
    _put(sc, "Ben", (80, 90))                       # 90 m
    dull = [{"channel": "sight", "acuity": "dulled"}]
    assert graded_sight(sc, "Ada", "Ben") == "conduct"
    assert graded_sight(sc, "Ada", "Ben", dull) == "shapes"   # half the reach, never none


# --------------------------------------------------------------------------
# What each channel carries at range
# --------------------------------------------------------------------------

def test_an_act_at_range_is_a_body_moving_and_a_dim_act_up_close_is_not():
    """The glove: seen at three metres in the dim, not at sixty in the sun."""
    from agents.perception import _sight_detail
    from world.spatial import spatial_rel_between
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (80, 0))                        # 60 m, lit
    rel = spatial_rel_between(sc, "Ada", "Ben")
    assert _sight_detail(sc, "Ada", "Ben", rel) == "shapes"
    _put(sc, "Ben", (4, 0))                         # 3 m
    assert _sight_detail(sc, "Ada", "Ben", rel) == "full"
    sc["rooms"]["square"]["light"] = "dim"
    assert visual_level_between(sc, "Ada", "Ben") == "conduct"
    assert _sight_detail(sc, "Ada", "Ben", rel) == "full"


def test_a_line_at_range_keeps_its_voice_and_loses_its_face():
    from agents.composer import speech_percept
    from world.spatial import spatial_rel_between
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (40, 0))                        # 30 m
    rel = spatial_rel_between(sc, "Ada", "Ben")
    entry = {"speaker": "Ben", "exact_quote": "Over here!", "volume": "shout",
             "tone": "with a crooked smirk"}
    far = speech_percept(entry, rel, "Ada", display="a figure", can_see=True,
                         face_seen=False, voice="a deep, rolling voice")
    assert far.data["manner"] == "a deep, rolling voice"     # first hearing: the register
    again = speech_percept(entry, rel, "Ada", display="a figure", can_see=True,
                           face_seen=False, voice="a deep, rolling voice",
                           prev_standing={far.data["voice_key"]})
    assert again.data["manner"] == ""                         # the smirk is a face
    near = speech_percept(entry, rel, "Ada", display="Ben", can_see=True,
                          face_seen=True, voice="a deep, rolling voice",
                          prev_standing={far.data["voice_key"]})
    assert near.data["manner"] == "with a crooked smirk"


def test_clothes_at_range_show_their_cut_and_not_their_ornaments():
    from story.attire import distant_region_surface
    surface = ("red wool coat — frayed at the cuffs, a mended elbow; "
               "silver brooch [worn at, covers nothing] — a hare in flight")
    assert distant_region_surface(surface) == "red wool coat"


def test_regions_at_range_are_delivered_coarse_and_concealed_only_far_off_or_dim():
    from agents.common import region_visibility
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (53, 0))                        # 40 m, lit: cut and colour
    verdicts = region_visibility(sc, "Ada", "Ben")
    assert not any("vantage" in (v.get("by") or {}) for v in verdicts.values())
    _put(sc, "Ben", (95, 95))                       # beyond 100 m: a figure
    reasons = {tuple((v.get("by") or {}).get("vantage") or ())
               for v in region_visibility(sc, "Ada", "Ben").values()}
    assert reasons == {("too far off to make out",)}
    _put(sc, "Ben", (53, 0))
    sc["rooms"]["square"]["light"] = "dim"
    reasons = {tuple((v.get("by") or {}).get("vantage") or ())
               for v in region_visibility(sc, "Ada", "Ben").values()}
    assert reasons == {("seen only in silhouette",)}


def _presence(sc, observer="Ada", known=None):
    from agents.composer import observer_display_map, presence_percepts
    co = [{"name": n, "appearance": "a tall fox-eared woman in a red coat"}
          for n in sc["positions"] if n != observer]
    labels = observer_display_map(sc, observer, co, known or {})
    return {p.source_label: p for p in presence_percepts(sc, observer, co, labels)}


def test_a_far_stranger_is_a_figure_some_way_off_and_a_known_one_keeps_their_name():
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (53, 0))
    (label, percept), = _presence(sc).items()
    assert label == "a figure" and percept.data["tier"] == "distant"
    (label, _p), = _presence(sc, known={"Ada": ["Ben"]}).items()
    assert label == "Ben"
    sc["rooms"]["square"]["light"] = "dim"
    _put(sc, "Ben", (4, 0))
    (label, percept), = _presence(sc).items()
    assert label == "an indistinct figure" and percept.data["tier"] != "distant"


def test_a_face_coming_into_reading_range_is_news():
    """Stepping inside fifteen metres turns "a figure some way off" into a
    face: the presence reads `changed`, never "still" -- the band edge has no
    hysteresis (a twin key that held it there claimed a continuity the view
    never gave, review 2026-10-04)."""
    from agents.composer import standing_verdicts
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (21, 0))                        # 15.75 m: conduct
    far = _presence(sc, known={"Ada": ["Ben"]})["Ben"]
    _put(sc, "Ben", (19, 0))                        # 14.25 m: full
    near = _presence(sc, known={"Ada": ["Ben"]})["Ben"]
    assert near.dedupe_key != far.dedupe_key
    assert standing_verdicts([near], {far.dedupe_key})[near.dedupe_key] == "changed"

# --------------------------------------------------------------------------
# Fixtures and things are named as far as their size carries
# --------------------------------------------------------------------------

def _yard_with(anchors, observer_cell=(0, 0)):
    sc = _square(anchors=anchors)
    _put(sc, "Ada", observer_cell)
    return sc


def test_a_small_fixture_far_off_is_not_named_and_a_large_one_is():
    from world.spatial import feature_visibility
    sc = _yard_with({
        "shrine": {"desc": "a small stone shrine", "dir": "e", "footprint": "point", "height": "floor"},
        "well": {"desc": "the old well", "dir": "e"},
    })
    rows = {r["anchor"]: r for r in feature_visibility(sc, "Ada", sweep=True)}
    far = [r for r in rows.values() if r.get("low_m", 0) > 20]
    assert far, "the fixture laid on the east wall must be far from the west corner"
    for r in far:
        if r["anchor"] == "shrine":
            assert not r["visible"] and r["basis"] == "distance"
        if r["anchor"] == "well":
            assert r["visible"]


def test_an_observer_with_no_station_cuts_no_fixture():
    from world.spatial import feature_visibility
    sc = _yard_with({"shrine": {"desc": "a small stone shrine", "dir": "e",
                                "footprint": "point", "height": "floor"}})
    sc["stations"]["Ada"] = {}
    assert all(r["basis"] != "distance" for r in feature_visibility(sc, "Ada", sweep=True))


def test_a_coin_on_a_far_counter_is_not_a_coin_and_a_lit_lantern_is_a_light():
    from agents.perception import _visible_things
    sc = _yard_with({"counter": {"desc": "the long counter", "dir": "e",
                                 "footprint": "large", "height": "waist"}})
    sc["entities"]["coin"] = {"name": "a silver coin", "portable": True,
                              "description": "a silver coin"}
    sc["positions"]["coin"] = "square"
    sc["stations"]["coin"] = {"at": "counter"}
    things = {r["uid"] for r in _visible_things(sc, "Ada", "square", sweep=True, bodies=["Ada"])}
    assert "coin" not in things
    sc["entities"]["lantern"] = {"name": "a hooded lantern", "portable": True,
                                 "light_source": "lit", "description": "a hooded lantern"}
    sc["positions"]["lantern"] = "square"
    sc["stations"]["lantern"] = {"at": "counter"}
    things = {r["uid"] for r in _visible_things(sc, "Ada", "square", sweep=True, bodies=["Ada"])}
    assert "lantern" in things
    from world.spatial import anchor_cells
    x, y = min(anchor_cells(sc, "square")["counter"]["cells"])
    _put(sc, "Ada", (x - 2, y))                     # beside the counter
    things = {r["uid"] for r in _visible_things(sc, "Ada", "square", sweep=True, bodies=["Ada"])}
    assert "coin" in things


# --------------------------------------------------------------------------
# Every observer through one grading
# --------------------------------------------------------------------------

def test_the_narrator_labels_a_body_as_the_players_view_did():
    from agents.narration import _earned_labels, _speaker_display

    class Ctx(dict):
        pass
    ctx = Ctx(perception_outcome={"company": {"player": [
        {"key": "k", "name": "Ben", "label": "a figure", "recognized": False}]}})
    earned = _earned_labels(ctx)
    assert _speaker_display("Ben", set(), "a tall fox-eared woman", [],
                            earned=earned) == "a figure"
    assert _speaker_display("Cara", set(), "a short man", [], earned=earned) != "a figure"


def test_a_body_in_another_room_is_in_that_room_in_japanese_too():
    from agents.composer import Percept, render_view
    p = Percept(kind="presence", channel="sight", source_label="Ben", fidelity="full",
                data={"tier": "beyond", "room": "台所", "side": None, "arc": "front",
                      "sight": "full", "body": "b1"},
                salience=0.35, dedupe_key="presence:b1:x")
    text = render_view([p], mode="player", full_render=True, language="ja").text
    assert "台所" in text and "ここ" not in text


def test_a_far_figure_reads_some_way_off_in_both_packs():
    from agents.composer import Percept, render_view
    def p(label):
        return Percept(kind="presence", channel="sight", source_label=label,
                       fidelity="degraded",
                       data={"tier": "distant", "side": None, "arc": "front",
                             "sight": "conduct", "body": "b2"},
                       salience=0.35, dedupe_key="presence:b2:x")
    assert render_view([p("a figure")], mode="player", full_render=True,
                       language="en").text == "A figure is some way off."
    assert "少し離れたところ" in render_view([p("人影")], mode="player",
                                         full_render=True, language="ja").text


def test_a_charter_witness_is_graded_as_it_was():
    """Distance does not shrink who witnesses a public act -- a living-world
    change left for the owner's ruling -- and nothing the distance evidence
    replaced for a view widens it either (`SightGrade.former`)."""
    from world.charter_observe import _witnesses
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (53, 0))                        # 40 m: a view reads conduct
    grade = sight_between(sc, "Ada", "Ben")
    assert grade.level == "conduct" and _witnesses(grade)
    gateway = sight_between(_gateway({"cell": [38, 5]}, {"cell": [59, 5]}), "Ada", "Ben")
    assert gateway.level == "conduct" and not _witnesses(gateway)   # the cone refused, still does
    assert _witnesses(sight_between(_two_rooms("near"), "Ada", "Ben"))
    assert not _witnesses(sight_between(_two_rooms("far"), "Ada", "Ben"))


# --------------------------------------------------------------------------
# The act channel: the card scales the bands and lifts nothing
# --------------------------------------------------------------------------

def _doorframe():
    """A lit medium hall and a lit large yard through an open door, the
    actor at a post on the door's own wall: the cone refuses him."""
    return {"rooms": {
        "hall": {"name": "hall", "desc": ".", "extent": {"w": 8, "d": 8},
                 "adjacent": [{"to": "yard", "barrier": "open_door", "dir": "e"}]},
        "yard": {"name": "yard", "desc": ".", "extent": {"w": 20, "d": 20},
                 "adjacent": [{"to": "hall", "barrier": "open_door", "dir": "w"}],
                 "anchors": {"post": {"desc": "a post", "dir": "w"}}}},
        "positions": {"Ada": "hall", "Ben": "yard"},
        "stations": {"Ben": {"at": "post"}}, "entities": {}}


def test_an_act_the_cone_refuses_across_a_doorway_is_not_delivered():
    """Probed 2026-10-04: the onset view delivered the whole surface of an
    act whose body the doorway cone refused."""
    from agents.perception import _sight_detail
    from world.spatial import spatial_rel_between
    sc = _doorframe()
    assert visual_level_between(sc, "Ada", "Ben") == "none"
    assert _sight_detail(sc, "Ada", "Ben", spatial_rel_between(sc, "Ada", "Ben")) == "none"


def test_keen_eyes_never_lift_a_crossing_into_the_acts_surface():
    """The "Long Gallery" leak: a body just through a locked door is a shape
    for a beat. A keen card reads further; it does not read through a door."""
    from agents.perception import _sight_detail
    from world.spatial import spatial_rel_between
    sc = {"rooms": {
        "hall": {"name": "hall", "desc": ".", "adjacent": [
            {"to": "study", "barrier": "closed_door", "locked": True, "dir": "n"}]},
        "study": {"name": "study", "desc": ".", "adjacent": [
            {"to": "hall", "barrier": "closed_door", "locked": True, "dir": "s"}]}},
        "positions": {"Edmund": "hall", "Ada": "study"}, "stations": {},
        "crossings": {"Ada": {"from": "hall", "to": "study", "beats": 2}},
        "entities": {}}
    keen = [{"channel": "sight", "acuity": "keen"}]
    assert visual_level_between(sc, "Edmund", "Ada") == "shapes"
    rel = spatial_rel_between(sc, "Edmund", "Ada")
    assert _sight_detail(sc, "Edmund", "Ada", rel, senses=keen) == "shapes"


def test_a_dark_act_at_range_is_no_more_legible_than_a_lit_one():
    from agents.perception import _sight_detail
    from world.spatial import spatial_rel_between
    sc = _square(light="dark")
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (80, 0))                        # 60 m in the dark
    rel = spatial_rel_between(sc, "Ada", "Ben")
    assert _sight_detail(sc, "Ada", "Ben", rel) == "shapes"
    _put(sc, "Ben", (2, 0))                         # beside her: the old carve-out
    assert _sight_detail(sc, "Ada", "Ben", rel) == "full"


def test_a_flier_high_over_the_gateway_is_never_read_at_arms_length():
    """The cone yields to a measured line only on certain evidence, and a
    body ninety metres up is ninety metres off."""
    sc = _gateway({"cell": [38, 5]}, {"cell": [1, 5], "altitude_m": 90})
    grade = sight_between(sc, "Ada", "Ben")
    assert grade.evidence.low > 85 and grade.level != "full"


def test_a_far_edge_between_two_big_rooms_is_read_at_its_farthest():
    """The old flat cap is replaced only where the far end of ALL the
    evidence -- the edge plus where each body can stand -- earns it."""
    def big(to, d):
        return {"name": to, "desc": ".", "exposure": "open", "extent": {"w": 60, "d": 30},
                "adjacent": [{"to": to, "barrier": "open", "dir": d, "distance": "far"}]}
    sc = {"rooms": {"a": big("b", "e"), "b": big("a", "w")},
          "positions": {"Ada": "a", "Ben": "b"}, "stations": {}, "entities": {}}
    grade = sight_between(sc, "Ada", "Ben")
    assert grade.evidence.far > 100 and grade.range == "shapes"


# --------------------------------------------------------------------------
# More of what the bands read
# --------------------------------------------------------------------------

def test_a_short_sighted_card_and_a_near_box():
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (14, 0))                        # 10.5 m
    assert graded_sight(sc, "Ada", "Ben") == "full"
    reduced = [{"channel": "sight", "range": "reduced"}]
    assert graded_sight(sc, "Ada", "Ben", reduced) == "conduct"
    from world.spatial import position_box
    sc["positions"]["Cara"] = "square"
    sc["stations"]["Cara"] = {"near": ["Ben"]}
    room, box, exact = position_box(sc, "Cara")
    assert box == (13, 0, 15, 1) and not exact      # within a pace of Ben's cell


def test_a_large_thing_is_named_further_and_a_put_out_light_is_not_a_light():
    from agents.perception import _visible_things
    from world.spatial import anchor_cells
    sc = _yard_with({"counter": {"desc": "the long counter", "dir": "e",
                                 "footprint": "large", "height": "waist"}})
    x, y = min(anchor_cells(sc, "square")["counter"]["cells"])
    _put(sc, "Ada", (max(0, x - 40), y))            # 30 m off
    for uid, record in (
            ("cart", {"name": "a handcart", "state": {"transit": {"to": "market"}},
                      "description": "a handcart"}),
            ("lamp", {"name": "a hooded lantern", "portable": True, "light_source": "lit",
                      "state": {"lit": "out"}, "description": "a hooded lantern"})):
        sc["entities"][uid] = record
        sc["positions"][uid] = "square"
        sc["stations"][uid] = {"at": "counter"}
    things = {r["uid"] for r in _visible_things(sc, "Ada", "square", sweep=True, bodies=["Ada"])}
    assert "cart" in things and "lamp" not in things


def test_a_motion_only_act_is_filed_as_ambiguous():
    from agents.composer import Percept, observations_from_render, render_view
    act = Percept(kind="act", channel="sight", source_label="a figure", fidelity="shapes",
                  data={"surface": ""}, salience=0.5, order_key=0, dedupe_key="act:x")
    rendered = render_view([act], mode="character", full_render=True)
    rows = observations_from_render("2", rendered)
    assert rows and rows[0]["fidelity"] == "ambiguous"


def test_two_far_strangers_are_two_figures_and_japanese_brief_names_the_room():
    from agents.composer import Percept, render_view
    def pres(body, label, **data):
        base = {"side": None, "arc": "front", "body": body, "sight": "conduct", "tier": "distant"}
        base.update(data)
        return Percept(kind="presence", channel="sight", source_label=label,
                       fidelity="degraded", data=base, salience=0.35,
                       dedupe_key="presence:%s:x" % body)
    two = [pres("b1", "a figure"), pres("b2", "a figure")]
    assert render_view(two, mode="player", full_render=True,
                       language="en").text == "Two figures are some way off."
    beyond = pres("b3", "Ben", tier="beyond", room="台所", sight="full")
    brief = render_view([beyond], mode="player", prev_standing={beyond.dedupe_key},
                        language="ja").text
    assert "ここ" not in brief


def test_seen_tells_need_the_face_and_heard_ones_do_not(temp_db):
    from types import SimpleNamespace
    from agents.perception import _delivered_manifest
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (53, 0))                        # 40 m
    ctx = SimpleNamespace(character_results={7: {"manifest": {
        "surface_demeanor": "amused", "tells": [
            {"cue": "a crooked smirk", "channel": "face", "subtlety": 0.0}]}}})
    sources = [{"name": "Ben", "room": "square"}]
    far = _delivered_manifest(ctx, sc, "Ada", sources, {}, {"Ben": 7})
    assert "Ben" not in far
    _put(sc, "Ben", (4, 0))                         # 3 m
    near = _delivered_manifest(ctx, sc, "Ada", sources, {}, {"Ben": 7})
    assert near["Ben"]["surface_demeanor"] == "amused"


def test_the_micro_round_labels_and_grades_a_far_stranger_as_the_view_does(temp_db):
    import json
    import time
    import agents.loops as loops
    from core.db import wset
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import default_character_data
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Far square", "", time.time()))
    cast = [{"id": cid, "sheet": json.dumps(default_character_data(name)),
             "cstate": "{}", "stance": "{}"}
            for cid, name in ((1, "Alice"), (2, "Bob"), (3, "Cara"))]
    sc = _square()
    _put(sc, "Alice", (0, 0))
    _put(sc, "Bob", (80, 0))                        # 60 m from Alice
    _put(sc, "Cara", (3, 0))
    sc.update({"location": "square", "time": "day", "attire": {}, "overlays": {}})
    wset(chat_id, "scene", sc)
    wset(chat_id, "known", {})
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Far square", scenario="", persona_id=None,
                      lorebook_id=None, created=time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="", created=time.time()),
        cast=cast, input="", director_interpret={"flow": {"reactors": [2, 3]}})
    observations = {}
    views, _ = loops.deterministic_micro_perception(
        ctx, 1, {"sequence": [{"type": "action", "observable": "raises a silver key"}]},
        sc, observation_out=observations)
    assert views[2] == ["A figure moves, too little of it to make out."]
    assert observations[2][0]["fidelity"] == "ambiguous"
    assert "silver key" in views[3][0] and not views[3][0].startswith("A figure")


# --------------------------------------------------------------------------
# The verification round (2026-10-05): what the fixes themselves broke
# --------------------------------------------------------------------------

def _yard_and_barn(barn_light="lit", pinned=False):
    def room(name, light, to, d):
        return {"name": name, "desc": ".", "light": light, "extent": {"w": 20, "d": 20},
                "adjacent": [{"to": to, "barrier": "open", "dir": d, "width": 4}]}
    sc = {"rooms": {"yard": room("the yard", "lit", "barn", "e"),
                    "barn": room("the barn", barn_light, "yard", "w")},
          "positions": {"Ada": "yard", "Ben": "barn"}, "stations": {}, "entities": {}}
    if pinned:
        # Just inside the doorway on each side: a doorway's cells are laid
        # along its wall by hash (rows 1-4 on the yard's side here), and the
        # field aligns the two sides' door cells.
        sc["stations"] = {"Ada": {"cell": [18, 2]}, "Ben": {"cell": [1, 15]}}
    return sc


def test_a_dulled_eye_the_cone_leaves_nothing_is_shown_no_act():
    from agents.perception import _sight_detail
    from world.spatial import spatial_rel_between
    sc = _yard_and_barn()
    dulled = [{"channel": "sight", "acuity": "dulled"}]
    assert graded_sight(sc, "Ada", "Ben", dulled) == "none"
    rel = spatial_rel_between(sc, "Ada", "Ben")
    assert _sight_detail(sc, "Ada", "Ben", rel, senses=dulled) == "none"
    assert _sight_detail(sc, "Ada", "Ben", rel) != "none"     # ordinary eyes: a shape


def test_sight_that_needs_no_light_sees_the_act_it_sees_the_body_in():
    from agents.perception import _sight_detail
    from world.spatial import spatial_rel_between
    sc = _yard_and_barn(barn_light="dark", pinned=True)
    sc["stations"]["Ben"] = {"cell": [8, 15]}       # past the doorway's spill, on its line
    owl = [{"channel": "sight", "needs_light": False}]
    rel = spatial_rel_between(sc, "Ada", "Ben")
    assert graded_sight(sc, "Ada", "Ben") == "none"
    assert _sight_detail(sc, "Ada", "Ben", rel) == "none"
    assert graded_sight(sc, "Ada", "Ben", owl) == "full"
    assert _sight_detail(sc, "Ada", "Ben", rel, senses=owl) == "full"


def test_a_distance_written_on_one_side_is_that_sides():
    """Read the way the old cap read it: the first edge that joins the
    rooms, from the observer's side, empty or not."""
    sc = _two_rooms("far")
    sc["rooms"]["a"]["adjacent"][0]["distance"] = ""
    assert visual_level_between(sc, "Ada", "Ben") == "full"
    assert visual_level_between(sc, "Ben", "Ada") == "conduct"


def test_japanese_brief_presence_names_the_room():
    from agents.composer import Percept, render_view
    beyond = Percept(kind="presence", channel="sight", source_label="Ben", fidelity="full",
                     data={"tier": "beyond", "room": "台所", "side": None, "arc": "front",
                           "sight": "full", "body": "b3"},
                     salience=0.35, dedupe_key="presence:b3:x")
    bell = Percept(kind="ambient", channel="hearing", source_label="",
                   fidelity="full", data={"desc": "鐘が鳴る。"}, salience=0.5,
                   order_key=1, dedupe_key="ambient:bell")
    text = render_view([beyond, bell], mode="player", prev_standing={beyond.dedupe_key},
                       language="ja").text
    assert "台所" in text and "ここ" not in text


def test_a_body_at_a_small_fixture_far_off_is_not_placed_at_it():
    from agents.composer import observer_display_map, presence_percepts
    sc = _square(anchors={"shrine": {"desc": "a small stone shrine", "dir": "e",
                                     "footprint": "point", "height": "floor"}})
    _put(sc, "Ada", (0, 48))
    sc["positions"]["Ben"] = "square"
    sc["stations"]["Ben"] = {"at": "shrine"}
    co = [{"name": "Ben", "appearance": "a tall man"}]
    (percept,) = presence_percepts(sc, "Ada", co, observer_display_map(sc, "Ada", co, {}))
    assert "at" not in percept.data


def test_a_small_fixture_in_the_next_room_far_off_is_not_named():
    from world.spatial import neighbour_feature_visibility
    sc = {"rooms": {
        "yard": {"name": "yard", "desc": ".", "exposure": "open", "extent": {"w": 40, "d": 10},
                 "adjacent": [{"to": "lane", "barrier": "open", "dir": "e", "width": 10}]},
        "lane": {"name": "lane", "desc": ".", "exposure": "open", "extent": {"w": 60, "d": 10},
                 "adjacent": [{"to": "yard", "barrier": "open", "dir": "w", "width": 10}],
                 "anchors": {"shrine": {"desc": "a small stone shrine", "dir": "e",
                                        "footprint": "point", "height": "floor"},
                             "well": {"desc": "the old well", "dir": "e"}}}},
        "positions": {"Ada": "yard"}, "stations": {"Ada": {"cell": [0, 5]}}, "entities": {}}
    named = {r["anchor"] for r in neighbour_feature_visibility(sc, "Ada", "lane", sweep=True) or []}
    assert "shrine" not in named and "well" in named


def test_clothes_at_range_reach_the_payload_coarse_and_without_parts():
    from agents.common import observer_body_regions
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (53, 0))                        # 40 m
    sc["attire"] = {"Ben": {"regions": {"torso": {"garments": [
        {"name": "red wool coat", "kind": "coat", "state": "worn", "coverage": "torso",
         "description": "frayed at the cuffs"}]}}}}
    tail = {"Ben": [{"kind": "tail", "count": 1, "at": "waist", "aspect": "back",
                     "through_clothing": True, "description": "russet"}]}
    (row,) = observer_body_regions(sc, "Ada", {"Ben": "a figure"}, extra_parts=tail)
    assert "red wool coat" in row["regions"]["torso"]
    assert "frayed" not in row["regions"]["torso"] and not row.get("parts")
    _put(sc, "Ben", (4, 0))                         # 3 m
    (row,) = observer_body_regions(sc, "Ada", {"Ben": "the tall man"}, extra_parts=tail)
    assert "frayed" in row["regions"]["torso"] and row.get("parts")


def test_the_opening_line_at_range_carries_no_smirk():
    from types import SimpleNamespace
    from agents.perception import _opening_line_percept
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (53, 0))
    ctx = SimpleNamespace(cast=[], chat=SimpleNamespace(id=0))
    entry = {"speaker": "Ben", "exact_quote": "Over here!", "volume": "shout",
             "tone": "with a crooked smirk"}
    kwargs = dict(field=None, recognized=set(), display_map={"Ben": "a figure"},
                  bodies_by_name={}, appearances={}, aliases={})
    p = {"room": "square"}
    far = _opening_line_percept(ctx, sc, p, "7", "Ada", entry, 0, **kwargs)
    assert far is not None and far.data["manner"] == ""
    _put(sc, "Ben", (4, 0))
    near = _opening_line_percept(ctx, sc, p, "7", "Ada", entry, 0, **kwargs)
    assert near.data["manner"] == "with a crooked smirk"


def test_a_present_tense_field_names_a_far_stranger_as_the_view_does(temp_db):
    """The orientation frame says "a figure" for the stranger the view calls
    one; the identity labeller -- an address, a past teller, lore -- keeps
    the descriptor, and a thing stays itself."""
    import json
    import time
    from agents.common import observer_label_fn, observer_view_label_fn
    from core.db import wset
    from story.character_schema import default_character_data
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Far square", "", time.time()))
    wset(chat_id, "known", {})
    ben = default_character_data("Ben")
    ben["embodiment"]["visible"] = {"summary": "a tall fox-eared woman"}
    cast = [{"id": 1, "sheet": json.dumps(default_character_data("Ada"))},
            {"id": 2, "sheet": json.dumps(ben)}]
    sc = _square()
    _put(sc, "Ada", (0, 0))
    _put(sc, "Ben", (80, 0))                        # 60 m
    sc["entities"]["fountain"] = {"name": "fountain", "kind": "fixture"}
    sc["positions"]["fountain"] = "square"
    chat = {"id": chat_id}
    view = observer_view_label_fn(chat, "Ada", cast, sc)
    ident = observer_label_fn(chat, "Ada", cast, scene=sc)
    assert view("Ben") == "a figure"
    assert ident("Ben") != "a figure" and ident("Ben") != "Ben"
    assert view("fountain") == ident("fountain") == "fountain"
